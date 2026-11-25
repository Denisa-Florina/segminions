import pytest

from app.core.errors import ValidationError
from app.schemas.patient import parse_age, to_patient_detail, to_patient_summary


def test_list_patients_requires_doctor_id(client):
    assert client.get("/api/patients").status_code == 400


@pytest.mark.parametrize("form", [
    {"name": "Ion Popescu", "age": "40"},              # missing doctor_id
    {"age": "40", "doctor_id": "doctor-1"},            # missing name
    {"name": "Ion Popescu", "age": "abc", "doctor_id": "doctor-1"},
    {"name": "Ion Popescu", "age": "200", "doctor_id": "doctor-1"},
])
def test_create_patient_rejects_invalid_input(client, form):
    assert client.post("/api/patients/", data=form).status_code == 400


def test_get_missing_patient_returns_404(client, no_patients):
    response = client.get("/api/patients/does-not-exist")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Patient not found"}


def test_update_missing_patient_returns_404(client, no_patients):
    response = client.put("/api/patients/does-not-exist", json={"name": "New name"})
    assert response.status_code == 404


def test_delete_missing_patient_returns_404(client, no_patients):
    assert client.delete("/api/patients/does-not-exist").status_code == 404


@pytest.mark.parametrize("raw, expected", [("1", 1), ("42", 42), (150, 150)])
def test_parse_age_accepts_valid_values(raw, expected):
    assert parse_age(raw) == expected


@pytest.mark.parametrize("raw", ["0", "151", "abc", None])
def test_parse_age_rejects_invalid_values(raw):
    with pytest.raises(ValidationError):
        parse_age(raw)


def test_patient_serialisation():
    patient = {
        "id": "p1", "name": "Ion", "age": 40, "date": "2026-11-25",
        "segmented": True, "metrics": {"confidence": 0.8, "voxel_count": 10},
    }
    assert to_patient_summary(patient) == {
        "id": "p1", "name": "Ion", "age": 40, "date": "2026-11-25",
        "dicomFile": "", "status": "completed", "confidence": 0.8,
    }
    assert to_patient_detail(patient)["metrics"]["voxel_count"] == 10
    assert to_patient_summary({**patient, "segmented": False})["status"] == "processing"
