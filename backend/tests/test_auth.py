from datetime import datetime, timedelta, timezone

import jwt

from tests.conftest import PASSWORD


def login(client, email="doctor@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_returns_a_token_and_only_public_doctor_fields(app, client, doctors):
    doctors["doctor-1"].update(reset_token="secret")      # must never reach the client
    body = login(client).get_json()

    assert set(body["doctor"]) == {"id", "name", "email", "specialization", "hospital"}
    payload = jwt.decode(body["token"], app.config["SECRET_KEY"], algorithms=["HS256"])
    assert payload["sub"] == "doctor-1"


def test_unknown_email_and_wrong_password_give_the_same_error(client, doctors):
    unknown = login(client, email="nobody@example.com")
    wrong = login(client, password="wrong")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.get_json() == wrong.get_json() == {"error": "Invalid email or password"}


def test_login_ignores_email_case_and_surrounding_spaces(client, doctors):
    assert login(client, email="  Doctor@Example.COM ").status_code == 200


def test_legacy_sha256_password_is_upgraded_to_bcrypt(client, doctors):
    assert login(client).status_code == 200
    assert doctors["doctor-1"]["password"].startswith("$2")   # now a bcrypt hash
    assert login(client).status_code == 200                    # and the new hash works


def test_invalid_or_expired_tokens_are_rejected(app, client):
    expired = jwt.encode(
        {"sub": "doctor-1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        app.config["SECRET_KEY"],
    )
    forged = jwt.encode({"sub": "doctor-1", "exp": 9999999999}, "wrong-secret")
    for token in ("not-a-jwt", forged, expired):
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
