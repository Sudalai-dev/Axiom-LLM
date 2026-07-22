"""Phase 12 — human-gated model-promotion governance.

No fine-tuned model is promoted automatically: a proposal starts PENDING, needs
an explicit human APPROVE/REJECT, and only an approved proposal can mint a
promotable model manifest. Includes the admin-only API loop.
"""

import pytest
from fastapi.testclient import TestClient

from api.gateway import create_gateway_app
from governance.model_governance import ModelGovernanceStore, ProposalState
from training.model_manifest import manifest_from_approved_proposal

app = create_gateway_app()


def _store(tmp_path):
    return ModelGovernanceStore(db_path=str(tmp_path / "gov.db"))


def _propose(store):
    return store.propose(
        model_name="axiom-qwen2.5:3b", base_model="Qwen/Qwen2.5-3B-Instruct",
        dataset_path="data/diagram_dataset.jsonl", dataset_examples=1319,
        hyperparameters={"lora_r": 16}, proposed_by="operator",
    )


# -- store invariants --------------------------------------------------------

def test_proposal_starts_pending_never_self_approved(tmp_path):
    store = _store(tmp_path)
    p = _propose(store)
    assert p.status == ProposalState.PENDING.value
    assert p.reviewed_by is None
    assert [x.proposal_id for x in store.list_pending()] == [p.proposal_id]


def test_approve_records_reviewer_and_mints_promotable_manifest(tmp_path):
    store = _store(tmp_path)
    p = _propose(store)
    approved = store.review(p.proposal_id, decision="approve", reviewer="admin", note="LGTM")
    assert approved.status == ProposalState.APPROVED.value
    assert approved.reviewed_by == "admin"
    assert approved.resolved_at
    assert store.list_pending() == []   # left the queue

    manifest = manifest_from_approved_proposal(approved, created_at="2026-07-21T00:00:00+00:00")
    assert manifest.is_promotable()
    assert manifest.approved_by == "admin"
    assert manifest.approval_ref == p.proposal_id


def test_rejected_proposal_cannot_mint_manifest(tmp_path):
    store = _store(tmp_path)
    p = _propose(store)
    rejected = store.review(p.proposal_id, decision="reject", reviewer="admin", note="regressed")
    assert rejected.status == ProposalState.REJECTED.value
    with pytest.raises(ValueError):
        manifest_from_approved_proposal(rejected, created_at="2026-07-21T00:00:00+00:00")


def test_cannot_review_twice_or_without_reviewer(tmp_path):
    store = _store(tmp_path)
    p = _propose(store)
    store.review(p.proposal_id, decision="approve", reviewer="admin")
    with pytest.raises(ValueError):
        store.review(p.proposal_id, decision="reject", reviewer="admin")   # already resolved
    q = _propose(store)
    with pytest.raises(ValueError):
        store.review(q.proposal_id, decision="approve", reviewer="")       # no human reviewer
    with pytest.raises(ValueError):
        store.review(q.proposal_id, decision="maybe", reviewer="admin")    # invalid decision


# -- admin API loop ----------------------------------------------------------

def _admin_headers(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_admin_can_propose_and_approve_via_api():
    with TestClient(app) as client:
        headers = _admin_headers(client)
        body = {
            "model_name": "axiom-qwen2.5:3b", "base_model": "Qwen/Qwen2.5-3B-Instruct",
            "dataset_path": "data/diagram_dataset.jsonl", "dataset_examples": 1319,
        }
        r = client.post("/api/v1/admin/model-proposals", headers=headers, json=body)
        assert r.status_code == 201
        pid = r.json()["proposal_id"]
        assert r.json()["status"] == "pending"

        # It's in the pending queue.
        pending = client.get("/api/v1/admin/model-proposals?status=pending", headers=headers).json()
        assert any(p["proposal_id"] == pid for p in pending)

        # Approve it — recorded human decision.
        rr = client.post(f"/api/v1/admin/model-proposals/{pid}/review",
                         headers=headers, json={"decision": "approve", "note": "ship it"})
        assert rr.status_code == 200
        assert rr.json()["status"] == "approved"
        assert rr.json()["reviewed_by"] == "admin"


def test_non_admin_cannot_access_model_governance():
    with TestClient(app) as client:
        client.post("/api/v1/auth/register", json={"username": "bob_gov", "password": "password123"})
        tok = client.post("/api/v1/auth/login",
                          json={"username": "bob_gov", "password": "password123"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {tok}"}
        r = client.post("/api/v1/admin/model-proposals", headers=headers, json={
            "model_name": "x", "base_model": "y", "dataset_path": "z", "dataset_examples": 1,
        })
        assert r.status_code == 403
