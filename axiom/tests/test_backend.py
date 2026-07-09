from fastapi.testclient import TestClient

from api.gateway import create_gateway_app

app = create_gateway_app()


def test_health_endpoint_is_available():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
