"""
Model-promotion governance (Phase 12).

A fine-tuned diagram model is never promoted to serving automatically. Every
promotion is a human decision recorded here: an operator PROPOSES a model change
(base model + which exported dataset + hyperparameters), it sits PENDING until a
reviewer explicitly APPROVES or REJECTS it, and only an approved proposal can
mint a promotable model manifest (training.model_manifest.ModelManifest).

There is deliberately NO auto-approve and NO retrain trigger anywhere in this
module — the loop is start → pending → human review → (approved | rejected).
Durable stdlib-sqlite store (same pattern as memory.learning_store).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from core.models.base import new_uuid


class ProposalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ModelChangeProposal:
    proposal_id: str
    model_name: str                 # e.g. "axiom-qwen2.5:3b"
    base_model: str                 # e.g. "Qwen/Qwen2.5-3B-Instruct"
    dataset_path: str
    dataset_examples: int
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    status: str = ProposalState.PENDING.value
    proposed_by: str = ""
    reviewed_by: Optional[str] = None
    review_note: str = ""
    created_at: str = ""
    resolved_at: Optional[str] = None

    @property
    def is_approved(self) -> bool:
        return self.status == ProposalState.APPROVED.value

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ModelGovernanceStore:
    """Durable, thread-safe queue of model-promotion proposals."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            data_dir = os.getenv("AXIOM_DATA_DIR", "data")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "model_governance.db")
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS model_change_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    base_model TEXT NOT NULL,
                    dataset_path TEXT NOT NULL,
                    dataset_examples INTEGER NOT NULL,
                    hyperparameters TEXT NOT NULL,
                    status TEXT NOT NULL,
                    proposed_by TEXT NOT NULL,
                    reviewed_by TEXT,
                    review_note TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mcp_status ON model_change_proposals (status)"
            )
            conn.commit()

    def _row(self, r) -> ModelChangeProposal:
        return ModelChangeProposal(
            proposal_id=r[0], model_name=r[1], base_model=r[2], dataset_path=r[3],
            dataset_examples=r[4], hyperparameters=json.loads(r[5]) if r[5] else {},
            status=r[6], proposed_by=r[7], reviewed_by=r[8], review_note=r[9] or "",
            created_at=r[10], resolved_at=r[11],
        )

    # -- write --------------------------------------------------------------

    def propose(
        self, *, model_name: str, base_model: str, dataset_path: str,
        dataset_examples: int, hyperparameters: Optional[Dict[str, Any]] = None,
        proposed_by: str,
    ) -> ModelChangeProposal:
        """Register a new promotion proposal. Always starts PENDING — proposing
        is never self-approving, even for the proposer."""
        proposal = ModelChangeProposal(
            proposal_id=new_uuid(),
            model_name=model_name, base_model=base_model, dataset_path=dataset_path,
            dataset_examples=int(dataset_examples), hyperparameters=hyperparameters or {},
            status=ProposalState.PENDING.value, proposed_by=proposed_by,
            created_at=_utc_now_iso(),
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO model_change_proposals (proposal_id, model_name, base_model, "
                "dataset_path, dataset_examples, hyperparameters, status, proposed_by, "
                "reviewed_by, review_note, created_at, resolved_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    proposal.proposal_id, model_name, base_model, dataset_path,
                    proposal.dataset_examples, json.dumps(proposal.hyperparameters),
                    proposal.status, proposed_by, None, "", proposal.created_at, None,
                ),
            )
            conn.commit()
        return proposal

    def review(
        self, proposal_id: str, *, decision: str, reviewer: str, note: str = "",
    ) -> ModelChangeProposal:
        """Approve or reject a pending proposal. Requires an explicit human
        ``reviewer``; a proposal can only be reviewed once, while PENDING."""
        decision = (decision or "").strip().lower()
        if decision not in ("approve", "reject"):
            raise ValueError("decision must be 'approve' or 'reject'")
        if not reviewer:
            raise ValueError("a human reviewer is required to review a proposal")
        new_status = ProposalState.APPROVED.value if decision == "approve" else ProposalState.REJECTED.value
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM model_change_proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"No such proposal: {proposal_id}")
            if row[0] != ProposalState.PENDING.value:
                raise ValueError(f"Proposal {proposal_id} is already {row[0]}, not pending")
            conn.execute(
                "UPDATE model_change_proposals SET status = ?, reviewed_by = ?, "
                "review_note = ?, resolved_at = ? WHERE proposal_id = ?",
                (new_status, reviewer, note, _utc_now_iso(), proposal_id),
            )
            conn.commit()
        return self.get(proposal_id)

    # -- read ---------------------------------------------------------------

    def get(self, proposal_id: str) -> Optional[ModelChangeProposal]:
        with self._lock, self._connect() as conn:
            r = conn.execute(
                "SELECT proposal_id, model_name, base_model, dataset_path, dataset_examples, "
                "hyperparameters, status, proposed_by, reviewed_by, review_note, created_at, "
                "resolved_at FROM model_change_proposals WHERE proposal_id = ?", (proposal_id,)
            ).fetchone()
        return self._row(r) if r else None

    def list_pending(self) -> List[ModelChangeProposal]:
        return self._list_where("WHERE status = ?", (ProposalState.PENDING.value,))

    def list_all(self) -> List[ModelChangeProposal]:
        return self._list_where("", ())

    def _list_where(self, clause: str, params) -> List[ModelChangeProposal]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT proposal_id, model_name, base_model, dataset_path, dataset_examples, "
                "hyperparameters, status, proposed_by, reviewed_by, review_note, created_at, "
                "resolved_at FROM model_change_proposals " + clause + " ORDER BY created_at DESC",
                params,
            ).fetchall()
        return [self._row(r) for r in rows]
