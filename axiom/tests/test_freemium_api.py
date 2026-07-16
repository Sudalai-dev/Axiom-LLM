"""End-to-end freemium tests: registration, daily quota 402 paywall, admin
grant, per-user key management, and billing status.

The free-chat limit is temporarily lowered to 1 on the shared entitlement
service so quota exhaustion is reached in two calls instead of six (keeping the
test fast); each solution call degrades to the deterministic synthesizer, so
these do not require a running OpenCode server.
"""

import uuid

from fastapi.testclient import TestClient

from api.gateway import create_gateway_app
from api.routes.deps import entitlement

app = create_gateway_app()

ENGINEERING_REQUEST = "Design an MQTT-based industrial sensor alerting platform for a factory"


def _admin_headers(client: TestClient) -> dict:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _register(client: TestClient) -> tuple[str, dict]:
    username = f"free_{uuid.uuid4().hex[:10]}"
    resp = client.post("/api/v1/auth/register", json={"username": username, "password": "password123"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["plan"] == "free"
    return username, {"Authorization": f"Bearer {body['access_token']}"}


def test_register_login_roundtrip():
    with TestClient(app) as client:
        username, _ = _register(client)
        # Wrong password rejected; correct password accepted.
        bad = client.post("/api/v1/auth/login", json={"username": username, "password": "wrong-password"})
        assert bad.status_code == 401
        good = client.post("/api/v1/auth/login", json={"username": username, "password": "password123"})
        assert good.status_code == 200
        assert good.json()["role"] == "end_user"


def test_free_quota_paywall_then_admin_grant_unblocks():
    with TestClient(app) as client:
        original_limit = entitlement._limit
        entitlement._limit = 1
        try:
            username, headers = _register(client)

            # 1st solution consumes the (lowered) daily quota.
            first = client.post("/api/v1/solution", headers=headers, json={"message": ENGINEERING_REQUEST})
            assert first.status_code == 200
            assert first.json()["is_conversational"] is False

            # 2nd solution hits the 402 paywall.
            blocked = client.post("/api/v1/solution", headers=headers, json={"message": ENGINEERING_REQUEST})
            assert blocked.status_code == 402
            body = blocked.json()
            assert body["status"] == 402
            assert body["upgrade_required"] is True
            assert body["free_chats_per_day"] == 1
            assert "renews_at" in body and body["renews_at"]

            # Admin grants the paid plan (manual payment path).
            admin = _admin_headers(client)
            grant = client.post(
                "/api/v1/billing/admin/grant",
                headers=admin,
                json={"username": username, "plan": "paid"},
            )
            assert grant.status_code == 200
            assert grant.json()["plan"] == "paid"

            # Paid user is no longer capped.
            after = client.post("/api/v1/solution", headers=headers, json={"message": ENGINEERING_REQUEST})
            assert after.status_code == 200
        finally:
            entitlement._limit = original_limit


def test_trivial_messages_do_not_consume_quota():
    with TestClient(app) as client:
        original_limit = entitlement._limit
        entitlement._limit = 1
        try:
            _, headers = _register(client)
            # Several trivial (conversational) messages — none should decrement.
            for _ in range(3):
                r = client.post("/api/v1/chat/messages", headers=headers, json={"message": "hello", "attachments": []})
                assert r.status_code == 200
                assert r.json()["is_conversational"] is True
            # The one real solution is still allowed afterward.
            r = client.post("/api/v1/solution", headers=headers, json={"message": ENGINEERING_REQUEST})
            assert r.status_code == 200
        finally:
            entitlement._limit = original_limit


def test_billing_status_shape_for_free_user():
    with TestClient(app) as client:
        _, headers = _register(client)
        resp = client.get("/api/v1/billing/status", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["plan"] == "free"
        assert body["unlimited"] is False
        assert body["payment_provider"] == "manual"
        assert "price_usd" in body


def test_user_api_key_stored_encrypted_and_never_echoed():
    with TestClient(app) as client:
        _, headers = _register(client)
        secret = "sk-test-ABCDEFGHIJKLMNOP1234"
        add = client.post("/api/v1/keys", headers=headers, json={"provider": "openai", "api_key": secret})
        assert add.status_code == 201
        view = add.json()
        assert view["provider"] == "openai"
        assert view["last4"] == secret[-4:]
        # The plaintext secret must never be returned.
        assert secret not in add.text

        listed = client.get("/api/v1/keys", headers=headers)
        assert listed.status_code == 200
        assert secret not in listed.text
        assert any(k["provider"] == "openai" and k["last4"] == secret[-4:] for k in listed.json())

        deleted = client.delete("/api/v1/keys/openai", headers=headers)
        assert deleted.status_code == 204


def test_admin_grant_requires_admin():
    with TestClient(app) as client:
        username, headers = _register(client)
        # A non-admin cannot grant paid plans.
        resp = client.post(
            "/api/v1/billing/admin/grant",
            headers=headers,
            json={"username": username, "plan": "paid"},
        )
        assert resp.status_code == 403
