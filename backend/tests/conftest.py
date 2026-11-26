import hashlib
from io import BytesIO

import pytest

from app import create_app
from app.config import TestingConfig
from app.core.security import create_access_token
from app.services.auth_service import auth_service
from app.services.patient_service import patient_service
from app.storage.file_storage import StoredFile

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
    monkeypatch.setattr(repo, "update_email", lambda doctor_id, email:
                        store[doctor_id].update(email=email))
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


@pytest.fixture
def files(monkeypatch):
    """In-memory replacement for scan/mask storage: {patient_id: {key: StoredFile}}."""
    store: dict[str, dict[str, StoredFile]] = {}

    def save(patient_id, stream, filename, key):
        data = stream.getvalue()
        store.setdefault(patient_id, {})[key] = StoredFile(data, filename, len(data))

    storage = patient_service.files
    monkeypatch.setattr(storage, "save", save)
    monkeypatch.setattr(storage, "load",
                        lambda patient_id, key: store.get(patient_id, {}).get(key))
    monkeypatch.setattr(storage, "delete",
                        lambda patient_id, key: store.get(patient_id, {}).pop(key, None))
    monkeypatch.setattr(storage, "delete_all", lambda patient_id: store.pop(patient_id, None))
    return store


class FakeSegmenter:
    """Stands in for the AI model: returns fixed metrics and a small mask."""

    def __init__(self):
        self.fail_with: Exception | None = None
        self.segmented = 0

    def check_scan(self, stream):
        pass

    def segment(self, stream):
        if self.fail_with:
            raise self.fail_with
        self.segmented += 1
        return {"confidence": 0.87, "voxel_count": 12}, BytesIO(b"mask-bytes")


@pytest.fixture
def segmenter(monkeypatch):
    fake = FakeSegmenter()
    monkeypatch.setattr(patient_service, "_segmenter_provider", lambda: fake)
    return fake
