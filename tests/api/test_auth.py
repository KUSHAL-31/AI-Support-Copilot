from fastapi.testclient import TestClient

from ai_support_copilot.api.main import app


def test_register_login_and_protected_me() -> None:
    client = TestClient(app)
    email = "security-test@example.com"
    password = "VerySecurePassword123!"

    register_response = client.post(
        "/auth/register",
        json={"tenant_id": "secure-acme", "email": email, "password": password},
    )
    assert register_response.status_code == 200
    token = register_response.json()["access_token"]

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["tenant_id"] == "secure-acme"

    login_response = client.post("/auth/token", json={"email": email, "password": password})
    assert login_response.status_code == 200
    assert login_response.json()["token_type"] == "bearer"


def test_query_requires_authentication() -> None:
    client = TestClient(app)

    response = client.post(
        "/query",
        json={"tenant_id": "secure-acme", "query": "How do we rotate keys?"},
    )

    assert response.status_code == 401


def test_tenant_mismatch_is_forbidden() -> None:
    client = TestClient(app)
    register_response = client.post(
        "/auth/register",
        json={
            "tenant_id": "tenant-a",
            "email": "tenant-a@example.com",
            "password": "VerySecurePassword123!",
        },
    )
    token = register_response.json()["access_token"]

    response = client.post(
        "/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "tenant-b", "query": "How do we rotate keys?"},
    )

    assert response.status_code == 403
