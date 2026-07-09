import pytest
from fastapi.testclient import TestClient

from api.gateway import create_gateway_app

app = create_gateway_app()

def test_cognitive_kernel_routing_paths():
    with TestClient(app) as client:
        # 1. Login to retrieve valid JWT token
        login_response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Test Path A: Low Complexity Conversational Query ("hello")
        chat_response_a = client.post(
            "/api/v1/chat/messages",
            headers=headers,
            json={"message": "hello", "attachments": []}
        )
        assert chat_response_a.status_code == 200
        data_a = chat_response_a.json()
        assert "response" in data_a
        assert "session_id" in data_a
        # Citations should be empty because grounding was bypassed
        assert len(data_a["citations"]) == 0

        # 3. Test Path B: High Complexity Query containing technical entities ("postgres")
        chat_response_b = client.post(
            "/api/v1/chat/messages",
            headers=headers,
            json={"message": "Explain the postgres database schema design", "attachments": []}
        )
        assert chat_response_b.status_code == 200
        data_b = chat_response_b.json()
        assert "response" in data_b
        assert "session_id" in data_b
        # Citations should be populated because grounding was retrieved
        assert len(data_b["citations"]) > 0
