"""API-level tests: /solution endpoint, developer-mode gating, chat integration."""

from fastapi.testclient import TestClient

import core.config
from api.gateway import create_gateway_app
from core.config import OutputConfig

app = create_gateway_app()

ENGINEERING_REQUEST = "Design an MQTT-based industrial sensor alerting platform for a factory"


def login(client: TestClient) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _enable_prose(monkeypatch):
    """AXIOM is diagrams-only by default; the prose document is retained behind a
    flag. Tests that assert the retained prose path opt in here."""
    monkeypatch.setattr(core.config.settings, "output", OutputConfig(prose_enabled=True))


def test_solution_default_is_diagrams_only():
    """New contract: the default response is the 8-diagram Blueprint with NO
    prose body (invariant B1 — the diagrams are the response)."""
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post("/api/v1/solution", headers=headers, json={"message": ENGINEERING_REQUEST})
        assert resp.status_code == 200
        data = resp.json()
        assert not data["is_conversational"]
        # Blueprint is the primary output: exactly 8 layer diagrams.
        assert len(data["blueprint"]["diagrams"]) == 8
        views = [d["view"] for d in data["blueprint"]["diagrams"]]
        assert views == [
            "perception", "context", "planning", "knowledge",
            "memory", "reasoning", "validation", "experience",
        ]
        # No prose body by default.
        assert data["markdown"] == ""
        assert data.get("solution_blueprint") in (None, {})


def test_solution_endpoint_returns_document_and_json(monkeypatch):
    _enable_prose(monkeypatch)
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post(
            "/api/v1/solution",
            headers=headers,
            json={"message": ENGINEERING_REQUEST},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert not data["is_conversational"]
        # Blueprint is present even in prose mode.
        assert len(data["blueprint"]["diagrams"]) == 8
        # Retained prose path (flag on).
        assert "## Executive Summary" in data["markdown"]
        assert "## Final Recommendations" in data["markdown"]
        assert data["solution_blueprint"]["technology_stack"]
        # Without developer_mode, no internals are exposed
        assert "developer" not in data


def test_solution_endpoint_returns_octagonal_visualization_for_every_user(monkeypatch):
    """The Octagonal Engineering Visualization is the primary output for
    ALL users — not gated behind developer_mode, unlike the cognitive trace."""
    _enable_prose(monkeypatch)  # this test also asserts the retained roadmap/docs
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post(
            "/api/v1/solution",
            headers=headers,
            json={"message": ENGINEERING_REQUEST},
        )
        data = resp.json()
        # Blueprint (new primary) available to every user, no developer_mode.
        assert len(data["blueprint"]["diagrams"]) == 8
        model = data["octagonal_model"]
        assert len(model["nodes"]) == 8
        assert len(model["edges"]) > 0
        domains = {n["domain"] for n in model["nodes"]}
        assert domains == {
            "perception", "context", "planning", "knowledge",
            "memory", "reasoning", "validation", "experience",
        }

        viz = data["visualizations"]
        assert viz["svg"].startswith("<svg")
        assert viz["svg"].count('data-domain="') == 8
        assert viz["mermaid"].startswith("flowchart")
        assert "@startuml" in viz["plantuml"]
        assert len(viz["reactflow"]["nodes"]) == 8
        assert len(viz["reactflow"]["edges"]) == len(model["edges"])
        assert len(viz["json_graph"]["nodes"]) == 8

        roadmap = data["implementation_roadmap"]
        assert roadmap["phases"]
        assert roadmap["phases"][0]["tasks"]

        docs = data["generated_documents"]
        assert {d["type"] for d in docs} == {"markdown", "json"}

        # The visualization describes the SOLUTION, never AXIOM's own
        # cognitive execution — no engine timeline/trace vocabulary anywhere.
        blob = str(data).lower()
        for leaked in ("engine_timeline", "cognitivecontext", "enginename", "engine_trace"):
            assert leaked not in blob


def test_solution_endpoint_conversational_reply_has_no_blueprint():
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post("/api/v1/solution", headers=headers, json={"message": "hello"})
        data = resp.json()
        assert data["is_conversational"]
        assert data["octagonal_model"] is None
        assert data["visualizations"] is None
        assert data["generated_documents"] == []


def test_solution_developer_mode_exposes_trace_for_admin():
    with TestClient(app) as client:
        headers = login(client)  # admin login
        resp = client.post(
            "/api/v1/solution",
            headers=headers,
            json={"message": ENGINEERING_REQUEST, "developer_mode": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        dev = data.get("developer")
        assert dev is not None
        assert 0.0 <= dev["confidence"] <= 1.0
        trace = dev["trace"]
        assert len(trace["engine_timeline"]) == 8
        assert trace["validation_report"]["passed"] is True


def test_chat_returns_solution_for_engineering_and_reply_for_trivial(monkeypatch):
    _enable_prose(monkeypatch)  # asserts the retained prose body
    with TestClient(app) as client:
        headers = login(client)

        # Trivial -> conversational, no citations
        resp_a = client.post(
            "/api/v1/chat/messages",
            headers=headers,
            json={"message": "hello", "attachments": []},
        )
        assert resp_a.status_code == 200
        data_a = resp_a.json()
        assert data_a["citations"] == []
        assert "## Executive Summary" not in data_a["response"]

        # Engineering -> full solution document with knowledge citations
        resp_b = client.post(
            "/api/v1/chat/messages",
            headers=headers,
            json={"message": "Explain the postgres database schema design", "attachments": []},
        )
        assert resp_b.status_code == 200
        data_b = resp_b.json()
        assert "## Executive Summary" in data_b["response"]
        assert len(data_b["citations"]) > 0


def test_chat_response_never_exposes_internal_stages():
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post(
            "/api/v1/chat/messages",
            headers=headers,
            json={"message": ENGINEERING_REQUEST, "attachments": []},
        )
        assert resp.status_code == 200
        lowered = resp.json()["response"].lower()
        for term in ("octagonal", "perception engine", "reasoning engine", "cognitive framework"):
            assert term not in lowered


def test_chat_engineering_response_carries_octagonal_visualization(monkeypatch):
    """Chat is no longer conversation-only: an engineering request's reply
    carries the Blueprint + Octagonal Visualization /solution returns."""
    _enable_prose(monkeypatch)  # asserts the retained roadmap/generated_documents
    with TestClient(app) as client:
        headers = login(client)

        trivial = client.post(
            "/api/v1/chat/messages", headers=headers, json={"message": "hello", "attachments": []}
        ).json()
        assert trivial["is_conversational"]
        assert trivial["octagonal_model"] is None

        engineering = client.post(
            "/api/v1/chat/messages", headers=headers,
            json={"message": ENGINEERING_REQUEST, "attachments": []},
        ).json()
        assert not engineering["is_conversational"]
        assert len(engineering["blueprint"]["diagrams"]) == 8  # new primary
        assert len(engineering["octagonal_model"]["nodes"]) == 8
        assert engineering["visualizations"]["svg"].startswith("<svg")
        assert engineering["implementation_roadmap"]["phases"]
        assert engineering["generated_documents"]
