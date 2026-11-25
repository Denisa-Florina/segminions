from datetime import datetime, timedelta, timezone

import jwt
import pytest

from tests.conftest import PASSWORD


def login(client, email="doctor@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"


def test_login_requires_email_and_password(client):
    response = client.post("/api/auth/login", json={"email": "doctor@example.com"})
    assert response.status_code == 400


def test_unknown_email_and_wrong_password_give_the_same_error(client, doctors):
    unknown = login(client, email="nobody@example.com")
    wrong = login(client, password="wrong")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.get_json() == wrong.get_json() == {"error": "Invalid email or password"}


def test_login_returns_token_and_no_password(app, client, doctors):
    response = login(client)
    assert response.status_code == 200
    body = response.get_json()
    assert "password" not in body["doctor"]

    payload = jwt.decode(body["token"], app.config["SECRET_KEY"], algorithms=["HS256"])
    assert payload["sub"] == "doctor-1"


def test_legacy_sha256_password_is_upgraded_to_bcrypt(client, doctors):
    assert login(client).status_code == 200
    assert doctors["doctor-1"]["password"].startswith("$2")   # now a bcrypt hash

    assert login(client).status_code == 200                    # bcrypt hash works
    assert login(client, password="wrong").status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_token(client, doctors, auth_headers):
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()["doctor"]["email"] == "doctor@example.com"


@pytest.mark.parametrize("header", [
    "Bearer not-a-jwt",
    "Basic dXNlcjpwYXNz",
    "Bearer " + jwt.encode({"sub": "doctor-1", "exp": 9999999999}, "wrong-secret"),
])
def test_invalid_tokens_are_rejected(client, header):
    response = client.get("/api/auth/me", headers={"Authorization": header})
    assert response.status_code == 401


def test_expired_token_is_rejected(app, client):
    expired = jwt.encode(
        {"sub": "doctor-1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        app.config["SECRET_KEY"],
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert "expired" in response.get_json()["error"]
