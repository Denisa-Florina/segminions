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


def test_invalid_or_expired_tokens_are_rejected(app, client):
    expired = jwt.encode(
        {"sub": "doctor-1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        app.config["SECRET_KEY"],
    )
    forged = jwt.encode({"sub": "doctor-1", "exp": 9999999999}, "wrong-secret")
    for token in ("not-a-jwt", forged, expired):
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


# --- Registration ------------------------------------------------------------

NEW_DOCTOR = {
    "name": "Dr. Ana Pop", "email": "  Ana.Pop@Example.com ", "password": "long enough pw",
    "specialization": "Radiology", "hospital": "",
}


def register(client, **overrides):
    return client.post("/api/auth/register", json={**NEW_DOCTOR, **overrides})


def test_register_creates_a_doctor_and_signs_them_in(app, client, doctors):
    response = register(client)
    assert response.status_code == 201
    body = response.get_json()

    assert body["doctor"]["email"] == "ana.pop@example.com"     # normalised
    assert body["doctor"]["hospital"] is None                    # empty -> not set
    assert "password" not in body["doctor"]
    payload = jwt.decode(body["token"], app.config["SECRET_KEY"], algorithms=["HS256"])
    assert payload["sub"] == body["doctor"]["id"]

    stored = doctors[body["doctor"]["id"]]
    assert stored["password"].startswith("$2")                  # bcrypt, never plain text
    # The new account can log in, with spaces in the password kept as typed.
    assert login(client, email="ana.pop@example.com", password="long enough pw").status_code == 200


def test_register_rejects_an_email_that_is_taken_in_any_case(client, doctors):
    response = register(client, email="DOCTOR@example.com")
    assert response.status_code == 409
    assert response.get_json() == {"error": "An account with this email already exists"}


def test_register_validates_input(client, doctors):
    cases = {
        "email": ["not-an-email", "a@b", "a b@example.com", "a@b@example.com"],
        "password": ["short", "x" * 73],
        "name": ["   "],
    }
    for field, values in cases.items():
        for value in values:
            response = register(client, **{field: value})
            assert response.status_code == 400, (field, value)
            assert response.get_json()["error"].startswith(field), (field, value)
    assert len(doctors) == 1                                     # nothing was created


def test_register_does_not_echo_the_password_in_errors(client, doctors):
    response = register(client, password="short")
    assert "short" not in response.get_json()["error"]
