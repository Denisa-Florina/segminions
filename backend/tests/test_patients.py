import pytest

from app.core.errors import ValidationError
from app.schemas.patient import (
    PatientCreate,
    PatientDetail,
    PatientSummary,
    PatientUpdate,
    validate_input,
)


def test_list_patients_requires_doctor_id(client):
    assert client.get("/api/patients").status_code == 400


@pytest.mark.parametrize("form, message", [
    ({"name": "Ion", "age": "40"}, "doctor_id is required"),
    ({"age": "40", "doctor_id": "d1"}, "name is required"),
    ({"name": "   ", "age": "40", "doctor_id": "d1"}, "name: String should have at least 1"),
    ({"name": "Ion", "age": "abc", "doctor_id": "d1"}, "age: Input should be a valid integer"),
    ({"name": "Ion", "age": "200", "doctor_id": "d1"}, "age: Input should be less than or equal"),
])
def test_create_patient_rejects_invalid_input(client, form, message):
    response = client.post("/api/patients/", data=form)
    assert response.status_code == 400
    assert message in response.get_json()["error"]


@pytest.mark.parametrize("body", [{"age": "abc"}, {"age": -5}, {"name": ""}])
def test_update_patient_rejects_invalid_values(client, body):
    # Previously these were written to Firestore unvalidated.
    assert client.put("/api/patients/p1", json=body).status_code == 400


def test_update_patient_requires_body(client):
    assert client.put("/api/patients/p1", json={}).status_code == 400


def test_get_missing_patient_returns_404(client, no_patients):
    response = client.get("/api/patients/does-not-exist")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Patient not found"}


def test_update_missing_patient_returns_404(client, no_patients):
    response = client.put("/api/patients/does-not-exist", json={"name": "New name"})
    assert response.status_code == 404


def test_delete_missing_patient_returns_404(client, no_patients):
    assert client.delete("/api/patients/does-not-exist").status_code == 404


# --- schemas ---------------------------------------------------------------

def test_patient_create_converts_form_strings():
    data = validate_input(PatientCreate, {"name": " Ion ", "age": "40", "doctor_id": "d1"})
    assert data == PatientCreate(name="Ion", age=40, doctor_id="d1")


def test_patient_update_keeps_only_sent_fields():
    updates = validate_input(PatientUpdate, {"name": "Ion", "unknown": "x"})
    assert updates.model_dump(exclude_unset=True, exclude_none=True) == {"name": "Ion"}


def test_validate_input_raises_app_validation_error():
    with pytest.raises(ValidationError, match="age: Input should be greater than or equal to 1"):
        validate_input(PatientCreate, {"name": "Ion", "age": 0, "doctor_id": "d1"})


PATIENT = {
    "id": "p1", "name": "Ion", "age": 40, "date": "2026-11-25", "doctor_id": "d1",
    "dicom_file": "scan.dcm", "segmented": True,
    "metrics": {"confidence": 0.8, "voxel_count": 10, "dice_score": 0.9},
}


def test_patient_summary_json_uses_camel_case():
    assert PatientSummary.from_db(PATIENT).to_json() == {
        "id": "p1", "name": "Ion", "age": 40, "date": "2026-11-25",
        "dicomFile": "scan.dcm", "status": "completed", "confidence": 0.8,
    }


def test_patient_summary_status_when_not_segmented():
    unsegmented = {**PATIENT, "segmented": False}
    assert PatientSummary.from_db(unsegmented).status == "processing"
    assert PatientSummary.from_db(unsegmented, unsegmented_status="pending").status == "pending"


def test_patient_detail_keeps_metrics_as_stored():
    metrics = PatientDetail.from_db(PATIENT).to_json()["metrics"]
    assert metrics["voxel_count"] == 10
    assert metrics["dice_score"] == 0.9   # the frontend reads metrics.dice_score


def test_patient_without_metrics():
    patient = {**PATIENT, "metrics": None, "segmented": False}
    assert PatientDetail.from_db(patient).to_json()["confidence"] == 0
