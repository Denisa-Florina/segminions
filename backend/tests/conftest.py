import hashlib

import pytest

from app import create_app
from app.config import TestingConfig
from app.core.security import create_access_token
from app.services.auth_service import auth_service
from app.services.patient_service import patient_service

PASSWORD = "correct-password"
LEGACY_SHA256_HASH = hashlib.sha256(PASSWORD.encode()).hexdigest()


@pytest.fixture
def app():
    return create_app(TestingConfig)


@pytest.fixture
def client(app):
    return app.test_client()


def make_auth_headers(app, doctor_id: str) -> dict:
    with app.app_context():
        return {"Authorization": f"Bearer {create_access_token(doctor_id)}"}


@pytest.fixture
def auth_headers(app):
    """Headers of an authenticated request made by doctor-1."""
    return make_auth_headers(app, "doctor-1")


@pytest.fixture
def doctors(monkeypatch):
    """In-memory replacement for the doctors collection."""
    store = {
        "doctor-1": {
            "id": "doctor-1", "email": "doctor@example.com",
            "name": "Dr. Test", "password": LEGACY_SHA256_HASH,
        },
    }
    repo = auth_service.doctors
    monkeypatch.setattr(repo, "get_by_email", lambda email: next(
        (dict(d) for d in store.values() if d["email"] == email), None))
    monkeypatch.setattr(repo, "get_by_id", lambda doctor_id: dict(store[doctor_id])
                        if doctor_id in store else None)
    monkeypatch.setattr(repo, "update_password_hash", lambda doctor_id, password_hash:
                        store[doctor_id].update(password=password_hash))
    return store


@pytest.fixture
def patients(monkeypatch):
    """In-memory replacement for the patients collection: p1 belongs to doctor-1,
    p2 to doctor-2."""
    store = {
        "p1": {"id": "p1", "name": "Ion", "age": 40, "date": "2026-11-25",
               "doctor_id": "doctor-1", "segmented": False, "metrics": {"confidence": 0}},
        "p2": {"id": "p2", "name": "Maria", "age": 55, "date": "2026-11-25",
               "doctor_id": "doctor-2", "segmented": False, "metrics": {"confidence": 0}},
    }

    def create(data):
        patient = {"id": f"p{len(store) + 1}", **data}
        store[patient["id"]] = patient
        return dict(patient)

    def update(patient_id, updates):
        if patient_id not in store:
            return None
        store[patient_id].update(updates)
        return dict(store[patient_id])

    repo = patient_service.patients
    monkeypatch.setattr(repo, "get", lambda pid: dict(store[pid]) if pid in store else None)
    monkeypatch.setattr(repo, "list_by_doctor",
                        lambda doctor_id: [dict(p) for p in store.values()
                                           if p["doctor_id"] == doctor_id])
    monkeypatch.setattr(repo, "create", create)
    monkeypatch.setattr(repo, "update", update)
    monkeypatch.setattr(repo, "delete", lambda pid: store.pop(pid, None))
    return store
