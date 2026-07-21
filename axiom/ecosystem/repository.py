"""
Engineering Knowledge Repository — the durable, versioned, graph-ready store at
the heart of the Engineering Knowledge Platform.

Self-contained stdlib sqlite3 (thread-locked, fail-soft, `AXIOM_DATA_DIR`),
mirroring `memory/learning_store.py` so the platform never depends on a
request-scoped DB session. Holds:

  * knowledge_objects        — the nodes (see ecosystem.models.KnowledgeObject)
  * knowledge_relationships  — typed edges (graph-ready)
  * knowledge_versions       — Git-like history + rollback
  * pending_knowledge        — the human approval queue (nothing auto-activates)
  * ontology_nodes           — hierarchical domain ontology
  * platform_meta            — small key/value store (e.g. the seeded marker)

Every write is fail-soft (never blocks the kernel); every read returns a safe
empty default on error.
"""

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from ecosystem.models import (
    COLUMNS,
    GLOBAL_SCOPE,
    ApprovalState,
    KnowledgeObject,
    Relationship,
    VersionRecord,
    stable_id,
    utc_now_iso,
)
from ecosystem.ranking import rank as rank_objects

# Which relationship types project onto which KnowledgeObject accessor.
_RELATION_ACCESSOR = {
    "applies_standard": "applicable_standards",
    "uses_technology": "applicable_technologies",
    "has_diagram": "related_diagrams",
    "has_component": "related_components",
    "has_document": "related_documents",
    "related_to": "related_knowledge",
}


class EngineeringKnowledgeRepository:
    """Thread-safe, fail-soft, durable store of engineering knowledge."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            data_dir = os.getenv("AXIOM_DATA_DIR", "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "engineering_knowledge.db")
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _rename_tenant_column(conn, table: str) -> None:
        """Migrate a pre-workspace store: rename legacy `tenant_id` → `user_id`
        in place (no-op on fresh or already-migrated DBs)."""
        try:
            existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            if "tenant_id" in existing and "user_id" not in existing:
                conn.execute(f"ALTER TABLE {table} RENAME COLUMN tenant_id TO user_id")
        except Exception:
            pass

    def _init_db(self) -> None:
        try:
            with self._lock, self._connect() as conn:
                # Legacy tenant_id → user_id (before any index touches user_id).
                self._rename_tenant_column(conn, "knowledge_objects")
                self._rename_tenant_column(conn, "pending_knowledge")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_objects (
                        knowledge_id TEXT PRIMARY KEY,
                        version INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        summary TEXT,
                        body TEXT,
                        category TEXT NOT NULL,
                        domain TEXT,
                        industry TEXT,
                        tags TEXT,
                        confidence REAL,
                        usage_count INTEGER,
                        success_rate REAL,
                        priority INTEGER,
                        freshness REAL,
                        rating REAL,
                        approval_count INTEGER,
                        approval_status TEXT,
                        author TEXT,
                        reviewer TEXT,
                        user_id TEXT,
                        source_document TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        attributes TEXT
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_ko_domain_cat ON knowledge_objects (domain, category)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_ko_user ON knowledge_objects (user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_ko_category ON knowledge_objects (category)")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_relationships (
                        source_id TEXT NOT NULL,
                        relation_type TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        PRIMARY KEY (source_id, relation_type, target_id)
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_source ON knowledge_relationships (source_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_target ON knowledge_relationships (target_id)")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS knowledge_versions (
                        knowledge_id TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        body TEXT,
                        attributes TEXT,
                        reviewer TEXT,
                        reason TEXT,
                        change_summary TEXT,
                        approval_notes TEXT,
                        created_at TEXT,
                        PRIMARY KEY (knowledge_id, version)
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS pending_knowledge (
                        pending_id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        submitted_by TEXT,
                        user_id TEXT,
                        status TEXT NOT NULL,
                        review_note TEXT,
                        reviewer TEXT,
                        created_at TEXT,
                        resolved_at TEXT
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_knowledge (status)")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ontology_nodes (
                        node_id TEXT PRIMARY KEY,
                        parent_id TEXT,
                        name TEXT NOT NULL,
                        domain TEXT,
                        level INTEGER
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_onto_parent ON ontology_nodes (parent_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_onto_name ON ontology_nodes (name)")
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS platform_meta (key TEXT PRIMARY KEY, value TEXT)"
                )
                conn.commit()
        except Exception:
            pass

    # -- knowledge objects --------------------------------------------------

    def upsert(self, obj: KnowledgeObject, write_version: bool = True) -> str:
        """Insert or replace a knowledge object. Fail-soft; returns its id."""
        try:
            with self._lock, self._connect() as conn:
                placeholders = ", ".join(["?"] * len(COLUMNS))
                conn.execute(
                    f"INSERT OR REPLACE INTO knowledge_objects ({', '.join(COLUMNS)}) "
                    f"VALUES ({placeholders})",
                    obj.to_row(),
                )
                if write_version:
                    conn.execute(
                        "INSERT OR REPLACE INTO knowledge_versions "
                        "(knowledge_id, version, body, attributes, reviewer, reason, "
                        "change_summary, approval_notes, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (obj.knowledge_id, obj.version, obj.body, json.dumps(obj.attributes),
                         obj.reviewer, "initial", "created", "", obj.updated_at),
                    )
                conn.commit()
        except Exception:
            pass
        return obj.knowledge_id

    def bulk_add(self, objects: List[KnowledgeObject]) -> int:
        n = 0
        for obj in objects:
            self.upsert(obj)
            n += 1
        return n

    def get(self, knowledge_id: str, hydrate: bool = True) -> Optional[KnowledgeObject]:
        try:
            with self._lock, self._connect() as conn:
                row = conn.execute(
                    f"SELECT {', '.join(COLUMNS)} FROM knowledge_objects WHERE knowledge_id = ?",
                    (knowledge_id,),
                ).fetchone()
        except Exception:
            return None
        if not row:
            return None
        obj = KnowledgeObject.from_row(row)
        if hydrate:
            self._hydrate_relations(obj)
        return obj

    def query(
        self,
        domain: Optional[str] = None,
        category: Optional[str] = None,
        industry: Optional[str] = None,
        text: Optional[str] = None,
        user_id: Optional[str] = None,
        approved_only: bool = True,
        ranked: bool = True,
        limit: int = 25,
    ) -> List[KnowledgeObject]:
        """Filtered, optionally rank-ordered query over the knowledge objects.

        Results always include GLOBAL_SCOPE ("*") knowledge plus, when
        `user_id` is given, that user's private knowledge.
        """
        clauses: List[str] = []
        params: List[Any] = []
        if domain:
            clauses.append("LOWER(domain) = ?")
            params.append(domain.lower())
        if category:
            clauses.append("category = ?")
            params.append(category)
        if industry:
            clauses.append("LOWER(industry) = ?")
            params.append(industry.lower())
        if approved_only:
            clauses.append("approval_status = ?")
            params.append(ApprovalState.APPROVED.value)
        if user_id:
            clauses.append("(user_id = ? OR user_id = ?)")
            params.extend([GLOBAL_SCOPE, user_id])
        if text:
            like = f"%{text.lower()}%"
            clauses.append("(LOWER(title) LIKE ? OR LOWER(summary) LIKE ? OR LOWER(body) LIKE ? OR LOWER(tags) LIKE ?)")
            params.extend([like, like, like, like])
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        # Pull a generous window, then rank in-process (ranking is richer than
        # anything expressible in SQL) and truncate.
        fetch = max(limit * 4, 100)
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    f"SELECT {', '.join(COLUMNS)} FROM knowledge_objects{where} "
                    f"ORDER BY updated_at DESC LIMIT ?",
                    (*params, fetch),
                ).fetchall()
        except Exception:
            return []
        objs = [KnowledgeObject.from_row(r) for r in rows]
        if ranked:
            objs = rank_objects(objs)
        return objs[:limit]

    def count(self, category: Optional[str] = None, domain: Optional[str] = None) -> int:
        clauses, params = [], []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if domain:
            clauses.append("LOWER(domain) = ?")
            params.append(domain.lower())
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        try:
            with self._lock, self._connect() as conn:
                row = conn.execute(
                    f"SELECT COUNT(*) FROM knowledge_objects{where}", tuple(params)
                ).fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def record_usage(self, knowledge_id: str, success: Optional[bool] = None) -> None:
        """Increment usage_count (and optionally fold a success signal into
        success_rate) so ranking reflects what actually gets used."""
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "UPDATE knowledge_objects SET usage_count = usage_count + 1 WHERE knowledge_id = ?",
                    (knowledge_id,),
                )
                if success is not None:
                    conn.execute(
                        "UPDATE knowledge_objects SET success_rate = "
                        "((success_rate * usage_count) + ?) / (usage_count + 1) "
                        "WHERE knowledge_id = ?",
                        (1.0 if success else 0.0, knowledge_id),
                    )
                conn.commit()
        except Exception:
            pass

    # -- versioning + rollback ----------------------------------------------

    def update(
        self,
        knowledge_id: str,
        changes: Dict[str, Any],
        reviewer: str = "",
        reason: str = "",
        change_summary: str = "",
        approval_notes: str = "",
    ) -> Optional[KnowledgeObject]:
        """Apply changes, bump the version, and snapshot the new version."""
        obj = self.get(knowledge_id, hydrate=False)
        if obj is None:
            return None
        for key, value in changes.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        obj.version += 1
        obj.updated_at = utc_now_iso()
        if reviewer:
            obj.reviewer = reviewer
        self.upsert(obj, write_version=False)
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO knowledge_versions "
                    "(knowledge_id, version, body, attributes, reviewer, reason, "
                    "change_summary, approval_notes, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (obj.knowledge_id, obj.version, obj.body, json.dumps(obj.attributes),
                     reviewer, reason, change_summary, approval_notes, obj.updated_at),
                )
                conn.commit()
        except Exception:
            pass
        return obj

    def versions(self, knowledge_id: str) -> List[VersionRecord]:
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    "SELECT knowledge_id, version, body, attributes, reviewer, reason, "
                    "change_summary, approval_notes, created_at FROM knowledge_versions "
                    "WHERE knowledge_id = ? ORDER BY version ASC",
                    (knowledge_id,),
                ).fetchall()
        except Exception:
            return []
        return [
            VersionRecord(
                knowledge_id=r[0], version=r[1], body=r[2],
                attributes=json.loads(r[3]) if r[3] else {}, reviewer=r[4],
                reason=r[5], change_summary=r[6], approval_notes=r[7], created_at=r[8],
            )
            for r in rows
        ]

    def rollback(self, knowledge_id: str, to_version: int, reviewer: str = "") -> Optional[KnowledgeObject]:
        """Restore an object's body/attributes from a prior version as a new
        version (Git-revert semantics — history is preserved, not rewritten)."""
        target = None
        for v in self.versions(knowledge_id):
            if v.version == to_version:
                target = v
                break
        if target is None:
            return None
        return self.update(
            knowledge_id,
            {"body": target.body, "attributes": target.attributes},
            reviewer=reviewer,
            reason=f"rollback to v{to_version}",
            change_summary=f"Restored content from version {to_version}",
        )

    # -- relationships (graph edges) ----------------------------------------

    def add_relationship(self, source_id: str, relation_type: str, target_id: str) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO knowledge_relationships "
                    "(source_id, relation_type, target_id) VALUES (?, ?, ?)",
                    (source_id, relation_type, target_id),
                )
                conn.commit()
        except Exception:
            pass

    def relationships(self, knowledge_id: str) -> List[Relationship]:
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    "SELECT source_id, relation_type, target_id FROM knowledge_relationships "
                    "WHERE source_id = ? OR target_id = ?",
                    (knowledge_id, knowledge_id),
                ).fetchall()
        except Exception:
            return []
        return [Relationship(source_id=r[0], relation_type=r[1], target_id=r[2]) for r in rows]

    def neighbors(self, knowledge_id: str, relation_type: Optional[str] = None) -> List[KnowledgeObject]:
        """One-hop outward traversal (source -> target)."""
        try:
            with self._lock, self._connect() as conn:
                if relation_type:
                    rows = conn.execute(
                        "SELECT target_id FROM knowledge_relationships "
                        "WHERE source_id = ? AND relation_type = ?",
                        (knowledge_id, relation_type),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT target_id FROM knowledge_relationships WHERE source_id = ?",
                        (knowledge_id,),
                    ).fetchall()
        except Exception:
            return []
        out = []
        for (target_id,) in rows:
            obj = self.get(target_id, hydrate=False)
            if obj:
                out.append(obj)
        return out

    def _hydrate_relations(self, obj: KnowledgeObject) -> None:
        """Project the edge table onto the object's relationship accessors."""
        for rel in self.relationships(obj.knowledge_id):
            if rel.source_id == obj.knowledge_id:
                accessor = _RELATION_ACCESSOR.get(rel.relation_type)
                if accessor:
                    getattr(obj, accessor).append(rel.target_id)
                if rel.relation_type == "parent_of":
                    obj.children.append(rel.target_id)
                if rel.relation_type == "child_of":
                    obj.parent = rel.target_id

    # -- pending approval queue ---------------------------------------------

    def submit_pending(self, obj: KnowledgeObject, submitted_by: str = "", pending_id: Optional[str] = None) -> str:
        """Queue a knowledge object for human review. It never becomes active
        knowledge until explicitly approved."""
        pending_id = pending_id or obj.knowledge_id
        obj.approval_status = ApprovalState.PENDING.value
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO pending_knowledge "
                    "(pending_id, payload, submitted_by, user_id, status, review_note, "
                    "reviewer, created_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (pending_id, json.dumps(obj.to_row()), submitted_by, obj.user_id,
                     ApprovalState.PENDING.value, "", "", utc_now_iso(), None),
                )
                conn.commit()
        except Exception:
            pass
        return pending_id

    def list_pending(self, user_id: Optional[str] = None, status: str = ApprovalState.PENDING.value) -> List[Dict[str, Any]]:
        clauses = ["status = ?"]
        params: List[Any] = [status]
        if user_id:
            clauses.append("(user_id = ? OR user_id = ?)")
            params.extend([GLOBAL_SCOPE, user_id])
        where = " WHERE " + " AND ".join(clauses)
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    f"SELECT pending_id, payload, submitted_by, user_id, status, "
                    f"review_note, reviewer, created_at FROM pending_knowledge{where} "
                    f"ORDER BY created_at DESC",
                    tuple(params),
                ).fetchall()
        except Exception:
            return []
        out = []
        for r in rows:
            obj = KnowledgeObject.from_row(tuple(json.loads(r[1])))
            out.append({
                "pending_id": r[0],
                "title": obj.title,
                "category": obj.category,
                "domain": obj.domain,
                "summary": obj.summary,
                "submitted_by": r[2],
                "user_id": r[3],
                "status": r[4],
                "review_note": r[5],
                "created_at": r[7],
            })
        return out

    def _get_pending_obj(self, conn, pending_id: str) -> Optional[KnowledgeObject]:
        row = conn.execute(
            "SELECT payload FROM pending_knowledge WHERE pending_id = ?", (pending_id,)
        ).fetchone()
        if not row:
            return None
        return KnowledgeObject.from_row(tuple(json.loads(row[0])))

    def approve_pending(self, pending_id: str, reviewer: str = "", note: str = "") -> Optional[KnowledgeObject]:
        """Promote a pending object into active knowledge (versioned)."""
        try:
            with self._lock, self._connect() as conn:
                obj = self._get_pending_obj(conn, pending_id)
                if obj is None:
                    return None
                conn.execute(
                    "UPDATE pending_knowledge SET status = ?, reviewer = ?, review_note = ?, "
                    "resolved_at = ? WHERE pending_id = ?",
                    (ApprovalState.APPROVED.value, reviewer, note, utc_now_iso(), pending_id),
                )
                conn.commit()
        except Exception:
            return None
        # Promote (bump version if it already existed) outside the lock — upsert
        # re-acquires it.
        existing = self.get(obj.knowledge_id, hydrate=False)
        obj.approval_status = ApprovalState.APPROVED.value
        obj.approval_count += 1
        obj.reviewer = reviewer
        obj.updated_at = utc_now_iso()
        obj.version = (existing.version + 1) if existing else 1
        self.upsert(obj, write_version=False)
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO knowledge_versions "
                    "(knowledge_id, version, body, attributes, reviewer, reason, "
                    "change_summary, approval_notes, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (obj.knowledge_id, obj.version, obj.body, json.dumps(obj.attributes),
                     reviewer, "approved", "Approved from pending queue", note, obj.updated_at),
                )
                conn.commit()
        except Exception:
            pass
        return obj

    def reject_pending(self, pending_id: str, reviewer: str = "", note: str = "") -> bool:
        try:
            with self._lock, self._connect() as conn:
                cur = conn.execute(
                    "UPDATE pending_knowledge SET status = ?, reviewer = ?, review_note = ?, "
                    "resolved_at = ? WHERE pending_id = ?",
                    (ApprovalState.REJECTED.value, reviewer, note, utc_now_iso(), pending_id),
                )
                conn.commit()
                return cur.rowcount > 0
        except Exception:
            return False

    # -- ontology nodes ------------------------------------------------------

    def add_ontology_node(self, node_id: str, name: str, parent_id: Optional[str], domain: str, level: int) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO ontology_nodes (node_id, parent_id, name, domain, level) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (node_id, parent_id, name, domain, level),
                )
                conn.commit()
        except Exception:
            pass

    def ontology_all(self) -> List[Dict[str, Any]]:
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    "SELECT node_id, parent_id, name, domain, level FROM ontology_nodes"
                ).fetchall()
        except Exception:
            return []
        return [
            {"node_id": r[0], "parent_id": r[1], "name": r[2], "domain": r[3], "level": r[4]}
            for r in rows
        ]

    # -- meta ----------------------------------------------------------------

    def meta_get(self, key: str) -> Optional[str]:
        try:
            with self._lock, self._connect() as conn:
                row = conn.execute("SELECT value FROM platform_meta WHERE key = ?", (key,)).fetchone()
                return row[0] if row else None
        except Exception:
            return None

    def meta_set(self, key: str, value: str) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO platform_meta (key, value) VALUES (?, ?)", (key, value)
                )
                conn.commit()
        except Exception:
            pass

    # -- analytics helpers ---------------------------------------------------

    def distinct_values(self, column: str) -> List[str]:
        if column not in ("domain", "industry", "category"):
            return []
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    f"SELECT DISTINCT {column} FROM knowledge_objects WHERE {column} != ''"
                ).fetchall()
                return [r[0] for r in rows if r[0]]
        except Exception:
            return []

    def category_counts(self) -> Dict[str, int]:
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    "SELECT category, COUNT(*) FROM knowledge_objects GROUP BY category"
                ).fetchall()
                return {r[0]: r[1] for r in rows}
        except Exception:
            return {}

    def domain_counts(self) -> Dict[str, int]:
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    "SELECT domain, COUNT(*) FROM knowledge_objects WHERE domain != '' GROUP BY domain"
                ).fetchall()
                return {r[0]: r[1] for r in rows}
        except Exception:
            return {}

    def most_used(self, limit: int = 5) -> List[KnowledgeObject]:
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    f"SELECT {', '.join(COLUMNS)} FROM knowledge_objects "
                    f"ORDER BY usage_count DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [KnowledgeObject.from_row(r) for r in rows]
        except Exception:
            return []

    def least_used(self, limit: int = 5) -> List[KnowledgeObject]:
        try:
            with self._lock, self._connect() as conn:
                rows = conn.execute(
                    f"SELECT {', '.join(COLUMNS)} FROM knowledge_objects "
                    f"ORDER BY usage_count ASC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [KnowledgeObject.from_row(r) for r in rows]
        except Exception:
            return []
