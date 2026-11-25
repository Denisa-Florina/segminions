import hashlib

import pytest

from app import create_app
from app.config import TestingConfig
from app.services.auth_service import auth_service
from app.services.patient_service import patient_service

DOCTOR = {
    "id": "doctor-1",
    "email": "doctor@example.com",
    "name": "Dr. Test",
    "password": hashlib.sha256(b"correct-password").hexdigest(),
}


@pytest.fixture
def app():
    return create_app(TestingConfig)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fake_doctors(monkeypatch):
    """Replace Firestore lookups for doctors with an in-memory doctor."""
    monkeypatch.setattr(
        auth_service.doctors, "get_by_email",
        lambda email: dict(DOCTOR) if email == DOCTOR["email"] else None,
    )
    monkeypatch.setattr(
        auth_service.doctors, "get_by_id",
        lambda doctor_id: dict(DOCTOR) if doctor_id == DOCTOR["id"] else None,
    )


@pytest.fixture
def no_patients(monkeypatch):
    """Make every patient lookup return 'not found' without touching Firestore."""
    monkeypatch.setattr(patient_service.patients, "get", lambda patient_id: None)
    monkeypatch.setattr(patient_service.patients, "update", lambda patient_id, updates: None)
