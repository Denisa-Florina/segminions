import pytest

from app.core.clock import utc_now


@pytest.mark.parametrize("method, url", [
    ("get", "/api/patients"),
    ("post", "/api/patients/"),
    ("get", "/api/patients/p1"),
    ("delete", "/api/patients/p1"),
    ("post", "/api/patients/p1/upload-dicom"),
    ("post", "/api/patients/p1/re-segment"),
    ("get", "/api/patients/p1/download/scan"),
    ("get", "/api/patients/p1/download/mask"),
    ("get", "/api/patients/p1/download/both"),
])
def test_every_patient_endpoint_requires_a_token(client, method, url):
    assert getattr(client, method)(url).status_code == 401


@pytest.mark.parametrize("method, url, kwargs", [
    ("get", "/api/patients/p2", {}),
    ("delete", "/api/patients/p2", {}),
    ("post", "/api/patients/p2/re-segment", {}),
    ("get", "/api/patients/p2/download/scan", {}),
])
def test_another_doctors_patient_is_not_found(client, patients, auth_headers, method, url, kwargs):
    response = getattr(client, method)(url, headers=auth_headers, **kwargs)
    assert response.status_code == 404
    assert patients["p2"]["name"] == "Maria"   # untouched


def test_new_patient_belongs_to_the_authenticated_doctor(client, patients, auth_headers):
    form = {"name": "Andrei", "age": "30", "doctor_id": "doctor-2"}   # attempt to spoof
    response = client.post("/api/patients/", data=form, headers=auth_headers)
    assert response.status_code == 201
    assert patients[response.get_json()["patient"]["id"]]["doctor_id"] == "doctor-1"


@pytest.mark.parametrize("form, message", [
    ({"age": "40"}, "name is required"),
    ({"name": "Ion", "age": "200"}, "age: Input should be less than or equal"),
])
def test_invalid_patient_data_is_rejected(client, auth_headers, form, message):
    response = client.post("/api/patients/", data=form, headers=auth_headers)
    assert response.status_code == 400
    assert message in response.get_json()["error"]


def test_delete_removes_the_stored_files_but_not_while_processing(
    client, patients, files, auth_headers
):
    files["p1"] = {"scan_data": object()}
    patients["p1"].update(status="processing", processing_started_at=utc_now())
    assert client.delete("/api/patients/p1", headers=auth_headers).status_code == 409

    patients["p1"]["status"] = "completed"
    assert client.delete("/api/patients/p1", headers=auth_headers).status_code == 204
    assert "p1" not in patients and "p1" not in files
