"""
Phase 6 (Multimodal Project Understanding) — API-level tests for the new,
additive POST /api/v1/projects/analyze upload endpoint. Confirms uploaded
project files drive the same Project Intelligence -> solution pipeline a
text request would, and that /api/v1/solution and /api/v1/chat/messages
remain completely unaffected (no modification to existing endpoints).
"""

import io
import zipfile

from fastapi.testclient import TestClient

from api.gateway import create_gateway_app

app = create_gateway_app()


def login(client: TestClient) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_analyze_endpoint_rejects_empty_request():
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post("/api/v1/projects/analyze", headers=headers, data={})
        assert resp.status_code == 400


def test_analyze_endpoint_with_markdown_file_produces_solution():
    with TestClient(app) as client:
        headers = login(client)
        md_content = (
            b"# Water Pump Predictive Maintenance\n"
            b"We operate factory water pumps and compressors and need vibration "
            b"sensor telemetry with MQTT alerting for predictive maintenance."
        )
        resp = client.post(
            "/api/v1/projects/analyze",
            headers=headers,
            files={"files": ("project_notes.md", io.BytesIO(md_content), "text/markdown")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert not data["is_conversational"]
        assert "## Executive Summary" in data["markdown"]
        assert data["project_diagrams"]
        assert len(data["project_diagrams"]) == 8
        assert data["ingested_files"][0]["filename"] == "project_notes.md"
        assert data["ingested_files"][0]["characters_extracted"] > 0


def test_analyze_endpoint_combines_message_and_file():
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post(
            "/api/v1/projects/analyze",
            headers=headers,
            data={"message": "Please prioritize security."},
            files={"files": ("notes.txt", io.BytesIO(b"Banking ledger transfer platform with fraud detection."), "text/plain")},
        )
        assert resp.status_code == 200
        assert not resp.json()["is_conversational"]


def test_analyze_endpoint_with_zip_archive():
    with TestClient(app) as client:
        headers = login(client)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("README.md", "# Hospital patient scheduling system")
            zf.writestr("service.py", "# clinical encounter workflow service")
        buf.seek(0)

        resp = client.post(
            "/api/v1/projects/analyze",
            headers=headers,
            files={"files": ("project.zip", buf, "application/zip")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert not data["is_conversational"]
        # Both members surfaced individually in the ingested-files summary.
        filenames = {f["filename"] for f in data["ingested_files"]}
        assert "README.md" in filenames
        assert "service.py" in filenames


def test_analyze_endpoint_with_image_only_degrades_gracefully_not_conversational_crash():
    from PIL import Image

    with TestClient(app) as client:
        headers = login(client)
        img_buf = io.BytesIO()
        Image.new("RGB", (10, 10), color="blue").save(img_buf, format="PNG")
        img_buf.seek(0)

        resp = client.post(
            "/api/v1/projects/analyze",
            headers=headers,
            data={"message": "Design a smart building occupancy platform."},
            files={"files": ("diagram.png", img_buf, "image/png")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert not data["is_conversational"]
        assert "no OCR/vision extraction" in data["ingested_files"][0]["note"]


def test_analyze_endpoint_with_only_unusable_file_returns_400():
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post(
            "/api/v1/projects/analyze",
            headers=headers,
            files={"files": ("archive.rar", io.BytesIO(b"junk"), "application/octet-stream")},
        )
        assert resp.status_code == 400


def test_existing_solution_endpoint_unaffected_by_new_route():
    with TestClient(app) as client:
        headers = login(client)
        resp = client.post(
            "/api/v1/solution",
            headers=headers,
            json={"message": "Design an MQTT-based industrial sensor alerting platform for a factory"},
        )
        assert resp.status_code == 200
        assert "developer" not in resp.json()
