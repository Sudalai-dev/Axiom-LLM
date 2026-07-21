"""
Persistent Learning Memory — durable record of successful conversations and
use-case/solution outcomes, spanning process restarts.

Backs the Memory Engine's `learning`, `decisions`, and `feedback` slices
(Master Prompt Part D) with a local SQLite file instead of in-process state.
Offers a lightweight similarity lookup (intent + entity overlap) so the
Reasoning Engine can recall — and stay consistent with — prior validated
solutions to similar problems, and records explicit user feedback so future
reasoning can see what worked and what didn't.

Uses stdlib sqlite3 directly (matching the precedent in
axiom.knowledge.graph.KnowledgeGraph) rather than the async SQLAlchemy models,
so OCIF engines stay self-contained and never depend on a request-scoped DB
session — per the Engine Contract, engines own their own state.
"""

import json
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LearningRecord:
    id: str
    user_id: str
    project: str
    intent: str
    entities: List[str]
    subject: str
    solution_title: str
    confidence: float
    tradeoffs: List[str] = field(default_factory=list)
    # Per-layer diagram STRUCTURE of the validated Blueprint (Phase 6): a list of
    # {"view","nodes","diagram_type"} the diagram core can reuse-and-adapt for a
    # similar future request. Only the structure is stored — mermaid is always
    # re-emitted deterministically, never replayed from storage (invariant B4).
    diagrams: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = ""


@dataclass
class FeedbackNote:
    id: str
    user_id: str
    project: str
    rating: int
    note: str
    created_at: str = ""


class LearningStore:
    """Thread-safe local SQLite store of validated outcomes and feedback."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            data_dir = os.getenv("AXIOM_DATA_DIR", "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "learning_memory.db")
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _rename_tenant_column(conn, table: str) -> None:
        """Migrate a pre-workspace store: rename the legacy `tenant_id` column to
        `user_id` in place. Runs before any index touches `user_id`."""
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "tenant_id" in existing and "user_id" not in existing:
            conn.execute(f"ALTER TABLE {table} RENAME COLUMN tenant_id TO user_id")

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            # Legacy tenant_id → user_id (no-op on fresh or already-migrated DBs).
            self._rename_tenant_column(conn, "learning_records")
            self._rename_tenant_column(conn, "feedback_notes")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_records (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    project TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    entities TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    solution_title TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    tradeoffs TEXT NOT NULL,
                    diagrams TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                )
                """
            )
            # Migration for stores created before Phase 6 (the CREATE above is a
            # no-op once the table exists, so add the column if it's missing).
            cols = {r[1] for r in conn.execute("PRAGMA table_info(learning_records)").fetchall()}
            if "diagrams" not in cols:
                conn.execute(
                    "ALTER TABLE learning_records ADD COLUMN diagrams TEXT NOT NULL DEFAULT '[]'"
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_learning_user_project "
                "ON learning_records (user_id, project)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback_notes (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    project TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    # -- learning records ---------------------------------------------------

    def record(
        self,
        record_id: str,
        user_id: str,
        project: str,
        intent: str,
        entities: List[str],
        subject: str,
        solution_title: str,
        confidence: float,
        tradeoffs: List[str],
        diagrams: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Persists a validated outcome. Fail-soft: never blocks the kernel."""
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO learning_records "
                    "(id, user_id, project, intent, entities, subject, solution_title, "
                    "confidence, tradeoffs, diagrams, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record_id, user_id, project, intent, json.dumps(entities),
                        subject, solution_title, confidence, json.dumps(tradeoffs),
                        json.dumps(diagrams or []), _utc_now_iso(),
                    ),
                )
                conn.commit()
        except Exception:
            pass

    def find_similar(
        self, user_id: str, project: str, intent: str, entities: List[str], limit: int = 3
    ) -> List[LearningRecord]:
        """
        Recalls past successful outcomes for this user/project, ranked by
        entity overlap with the current request, falling back to same-intent
        recency. Records with no overlap at all are excluded.
        """
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, user_id, project, intent, entities, subject, solution_title, "
                    "confidence, tradeoffs, diagrams, created_at FROM learning_records "
                    "WHERE user_id = ? AND project = ? ORDER BY created_at DESC LIMIT 200",
                    (user_id, project),
                ).fetchall()
        except Exception:
            return []

        entity_set = set(entities)
        scored = []
        for row in rows:
            row_entities = json.loads(row[4]) if row[4] else []
            overlap = len(entity_set & set(row_entities))
            same_intent = row[3] == intent
            score = overlap * 2 + (1 if same_intent else 0)
            if score <= 0:
                continue
            scored.append((score, LearningRecord(
                id=row[0], user_id=row[1], project=row[2], intent=row[3],
                entities=row_entities, subject=row[5], solution_title=row[6],
                confidence=row[7], tradeoffs=json.loads(row[8]) if row[8] else [],
                diagrams=json.loads(row[9]) if row[9] else [],
                created_at=row[10],
            )))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [rec for _, rec in scored[:limit]]

    def iter_records(
        self, user_id: Optional[str] = None, project: Optional[str] = None
    ) -> List[LearningRecord]:
        """Return every persisted record (optionally scoped to a user/project),
        newest first — the full-corpus read the dataset exporter needs (unlike
        find_similar, which ranks by entity overlap)."""
        clauses, params = [], []
        if user_id:
            clauses.append("user_id = ?"); params.append(user_id)
        if project:
            clauses.append("project = ?"); params.append(project)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, user_id, project, intent, entities, subject, solution_title, "
                    "confidence, tradeoffs, diagrams, created_at FROM learning_records"
                    + where + " ORDER BY created_at DESC",
                    tuple(params),
                ).fetchall()
        except Exception:
            return []
        return [
            LearningRecord(
                id=r[0], user_id=r[1], project=r[2], intent=r[3],
                entities=json.loads(r[4]) if r[4] else [], subject=r[5],
                solution_title=r[6], confidence=r[7],
                tradeoffs=json.loads(r[8]) if r[8] else [],
                diagrams=json.loads(r[9]) if r[9] else [],
                created_at=r[10],
            )
            for r in rows
        ]

    def count(self, user_id: Optional[str] = None) -> int:
        """Number of persisted learning records, optionally scoped to a user."""
        try:
            with self._lock, self._connect() as conn:
                if user_id:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM learning_records WHERE user_id = ?", (user_id,)
                    ).fetchone()
                else:
                    row = conn.execute("SELECT COUNT(*) FROM learning_records").fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    # -- feedback notes -------------------------------------------------------

    def record_feedback(self, note_id: str, user_id: str, project: str, rating: int, note: str) -> None:
        """Persists explicit user feedback on a prior response. Fail-soft."""
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO feedback_notes "
                    "(id, user_id, project, rating, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (note_id, user_id, project, rating, note, _utc_now_iso()),
                )
                conn.commit()
        except Exception:
            pass

    def recent_feedback(self, user_id: str, project: str, limit: int = 5) -> List[FeedbackNote]:
        """Returns the most recent feedback notes for this user/project."""
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, user_id, project, rating, note, created_at FROM feedback_notes "
                    "WHERE user_id = ? AND project = ? ORDER BY created_at DESC LIMIT ?",
                    (user_id, project, limit),
                ).fetchall()
        except Exception:
            return []
        return [FeedbackNote(id=r[0], user_id=r[1], project=r[2], rating=r[3], note=r[4], created_at=r[5]) for r in rows]
