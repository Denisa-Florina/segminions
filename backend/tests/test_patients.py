from io import BytesIO

import pytest

from app.core.errors import ValidationError
from app.schemas.patient import (
    PatientCreate,
    PatientDetail,
    PatientSummary,
    PatientUpdate,
    validate_input,
)
from tests.conftest import make_auth_headers

# --- authentication --------------------------------------------------------

@pytest.mark.parametrize("method, url", [
    ("get", "/api/patients"),
    ("post", "/api/patients/"),
    ("get", "/api/patients/p1"),
    ("put", "/api/patients/p1"),
    ("delete", "/api/patients/p1"),
    ("post", "/api/patients/p1/upload-dicom"),
    ("post", "/api/patients/p1/re-segment"),
    ("get", "/api/patients/p1/download/scan"),
    ("get", "/api/patients/p1/download/mask"),
    ("get", "/api/patients/p1/download/both"),
])
def test_every_patient_endpoint_requires_a_token(client, method, url):
    assert getattr(client, method)(url).status_code == 401


def test_cors_preflight_does_not_require_a_token(client):
    response = client.options(
        "/api/patients",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200


# --- authorization: a doctor only sees their own patients -------------------

def test_list_returns_only_own_patients(client, patients, auth_headers):
    # The doctor_id query parameter is ignored; the token decides.
    response = client.get("/api/patients?doctor_id=doctor-2", headers=auth_headers)
    assert response.status_code == 200
    assert [p["id"] for p in response.get_json()["patients"]] == ["p1"]


def test_get_own_patient(client, patients, auth_headers):
    response = client.get("/api/patients/p1", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()["patient"]["name"] == "Ion"


@pytest.mark.parametrize("method, url, kwargs", [
    ("get", "/api/patients/p2", {}),
    ("put", "/api/patients/p2", {"json": {"name": "Hacked"}}),
    ("delete", "/api/patients/p2", {}),
    ("post", "/api/patients/p2/re-segment", {}),
    ("get", "/api/patients/p2/download/scan", {}),
    ("get", "/api/patients/p2/download/both", {}),
])
def test_other_doctors_patient_is_not_found(client, patients, auth_headers, method, url, kwargs):
    response = getattr(client, method)(url, headers=auth_headers, **kwargs)
    assert response.status_code == 404
    assert response.get_json() == {"error": "Patient not found"}
    assert patients["p2"]["name"] == "Maria"   # untouched


def test_create_assigns_patient_to_authenticated_doctor(client, patients, auth_headers):
    form = {"name": "Andrei", "age": "30", "doctor_id": "doctor-2"}   # attempt to spoof
    response = client.post("/api/patients/", data=form, headers=auth_headers)
    assert response.status_code == 201
    created_id = response.get_json()["patient"]["id"]
    assert patients[created_id]["doctor_id"] == "doctor-1"


def test_update_and_delete_own_patient(app, client, patients, auth_headers):
    response = client.put("/api/patients/p1", json={"name": "Ion Pop"}, headers=auth_headers)
    assert response.status_code == 200
    assert patients["p1"]["name"] == "Ion Pop"

    assert client.delete("/api/patients/p1", headers=auth_headers).status_code == 200
    assert "p1" not in patients


def test_doctor_2_cannot_see_doctor_1_patients(app, client, patients):
    headers = make_auth_headers(app, "doctor-2")
    assert client.get("/api/patients/p1", headers=headers).status_code == 404
    listed = client.get("/api/patients", headers=headers).get_json()["patients"]
    assert [p["id"] for p in listed] == ["p2"]


# --- input validation ------------------------------------------------------

@pytest.mark.parametrize("form, message", [
    ({"age": "40"}, "name is required"),
    ({"name": "   ", "age": "40"}, "name: String should have at least 1"),
    ({"name": "Ion", "age": "abc"}, "age: Input should be a valid integer"),
    ({"name": "Ion", "age": "200"}, "age: Input should be less than or equal"),
])
def test_create_patient_rejects_invalid_input(client, auth_headers, form, message):
    response = client.post("/api/patients/", data=form, headers=auth_headers)
    assert response.status_code == 400
    assert message in response.get_json()["error"]


def test_create_patient_rejects_too_many_files(app, client, auth_headers):
    app.config["MAX_DICOM_FILES"] = 2
    files = [(BytesIO(b"x"), f"slice{i}.dcm") for i in range(3)]
    response = client.post(
        "/api/patients/", headers=auth_headers,
        data={"name": "Ion", "age": "40", "dicom_file": files},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "Too many files" in response.get_json()["error"]


@pytest.mark.parametrize("body", [{"age": "abc"}, {"age": -5}, {"name": ""}])
def test_update_patient_rejects_invalid_values(client, patients, auth_headers, body):
    assert client.put("/api/patients/p1", json=body, headers=auth_headers).status_code == 400


def test_update_patient_requires_body(client, auth_headers):
    assert client.put("/api/patients/p1", json={}, headers=auth_headers).status_code == 400


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
