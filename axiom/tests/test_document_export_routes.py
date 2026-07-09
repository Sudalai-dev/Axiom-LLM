"""API-level tests for the on-demand document/export endpoints and the
dashboard-first fields added to /solution and /chat/messages."""

from fastapi.testclient import TestClient

from api.gateway import create_gateway_app

app = create_gateway_app()

ENGINEERING_REQUEST = "Design a Kafka-based order processing pipeline"


def login(client: TestClient) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def create_solution(client: TestClient, headers: dict) -> dict:
    resp = client.post("/api/v1/solution", headers=headers, json={"message": ENGINEERING_REQUEST})
    assert resp.status_code == 200
    return resp.json()


def test_solution_response_carries_dashboard_and_catalogs():
    with TestClient(app) as client:
        headers = login(client)
        data = create_solution(client, headers)

        # New dashboard-first fields
        assert data["dashboard"]["executive_summary"]
        assert len(data["dashboard"]["octagon_navigation"]) == 8
        assert data["documents_catalog"]
        assert data["export_manifest"]

        # Backward-compat fields unchanged
        assert data["solution_blueprint"]["technology_stack"] is not None
        assert data["octagonal_model"]["nodes"]
        assert data["visualizations"]["svg"].startswith("<svg")


def test_chat_response_also_carries_dashboard_fields():
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post(
            "/api/v1/chat/messages", headers=headers,
            json={"message": ENGINEERING_REQUEST, "attachments": []},
        )
        data = resp.json()
        assert data["dashboard"] is not None
        assert data["documents_catalog"]
        assert data["export_manifest"]

        trivial = client.post(
            "/api/v1/chat/messages", headers=headers, json={"message": "hello", "attachments": []}
        ).json()
        assert trivial["dashboard"] is None
        assert trivial["documents_catalog"] == []


def test_list_documents_for_solution():
    with TestClient(app) as client:
        headers = login(client)
        data = create_solution(client, headers)
        resp = client.get(f"/api/v1/solutions/{data['solution_id']}/documents", headers=headers)
        assert resp.status_code == 200
        docs = resp.json()["documents"]
        assert len(docs) == 15


def test_render_specific_document_type():
    with TestClient(app) as client:
        headers = login(client)
        data = create_solution(client, headers)
        resp = client.get(f"/api/v1/solutions/{data['solution_id']}/documents/hld", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "High-Level Design" in body["title"]
        assert body["content"]


def test_unknown_document_type_returns_404():
    with TestClient(app) as client:
        headers = login(client)
        data = create_solution(client, headers)
        resp = client.get(f"/api/v1/solutions/{data['solution_id']}/documents/not-a-type", headers=headers)
        assert resp.status_code == 404


def test_unknown_solution_id_returns_404():
    with TestClient(app) as client:
        headers = login(client)
        resp = client.get("/api/v1/solutions/does-not-exist/documents", headers=headers)
        assert resp.status_code == 404
        resp2 = client.get("/api/v1/solutions/does-not-exist/documents/hld", headers=headers)
        assert resp2.status_code == 404
        resp3 = client.get("/api/v1/solutions/does-not-exist/export/svg", headers=headers)
        assert resp3.status_code == 404


def test_export_formats_available_and_unavailable():
    with TestClient(app) as client:
        headers = login(client)
        data = create_solution(client, headers)
        sid = data["solution_id"]

        for fmt in ("svg", "mermaid", "plantuml", "json_graph", "reactflow", "markdown", "json", "html"):
            resp = client.get(f"/api/v1/solutions/{sid}/export/{fmt}", headers=headers)
            assert resp.status_code == 200, f"{fmt} failed: {resp.text}"
            assert resp.json()["format"] == fmt

        for fmt in ("pdf", "png"):
            resp = client.get(f"/api/v1/solutions/{sid}/export/{fmt}", headers=headers)
            assert resp.status_code == 501


def test_openapi_document_is_a_distinct_endpoint_shape():
    with TestClient(app) as client:
        headers = login(client)
        data = create_solution(client, headers)
        resp = client.get(f"/api/v1/solutions/{data['solution_id']}/documents/openapi", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["type"] == "openapi"
        assert resp.json()["filename"].endswith(".json")
