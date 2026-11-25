def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "healthy"


def test_login_requires_email_and_password(client):
    response = client.post("/api/auth/login", json={"email": "doctor@example.com"})
    assert response.status_code == 400


def test_login_with_unknown_email_returns_401(client, fake_doctors):
    response = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert response.status_code == 401


def test_login_with_wrong_password_returns_401(client, fake_doctors):
    response = client.post(
        "/api/auth/login", json={"email": "doctor@example.com", "password": "wrong"}
    )
    assert response.status_code == 401


def test_login_success_does_not_return_password(client, fake_doctors):
    response = client.post(
        "/api/auth/login", json={"email": "doctor@example.com", "password": "correct-password"}
    )
    assert response.status_code == 200
    doctor = response.get_json()["doctor"]
    assert doctor["id"] == "doctor-1"
    assert "password" not in doctor


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_after_login(client, fake_doctors):
    client.post(
        "/api/auth/login", json={"email": "doctor@example.com", "password": "correct-password"}
    )
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.get_json()["doctor"]["email"] == "doctor@example.com"
