"""Feedback route: explicit user ratings persist into learning memory."""

from fastapi.testclient import TestClient

from api.gateway import create_gateway_app
from api.routes.deps import learning_store

app = create_gateway_app()


def login(client: TestClient) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_feedback_submission_persists_into_learning_store():
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post(
            "/api/v1/feedback",
            headers=headers,
            json={"session_id": "session-123", "rating": 1, "note": "Very helpful architecture"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "success"
        assert body["feedback_id"]

        notes = learning_store.recent_feedback(
            user_id="00000000-0000-0000-0000-000000000001", project="default"
        )
        assert any("Very helpful architecture" in n.note for n in notes)


def test_feedback_requires_valid_rating():
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post(
            "/api/v1/feedback",
            headers=headers,
            json={"session_id": "session-123", "rating": 5},
        )
        assert resp.status_code == 422
