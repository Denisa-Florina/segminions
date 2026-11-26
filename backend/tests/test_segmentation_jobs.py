"""Background segmentation: status flow, failures, stale jobs, and the job queue.

TestingConfig runs jobs inline, so a job has finished when the request returns; the
response still shows the state at the moment the job was queued."""

import threading
import time
from io import BytesIO

import pytest

from app.core.errors import ServiceUnavailableError
from app.core.job_queue import JobQueue
from app.ml.errors import InvalidScanError
from app.services.patient_service import (
    PROCESSING_INTERRUPTED,
    SEGMENTATION_FAILED,
    patient_service,
)
from tests.test_dicom_converter import make_dicom_slice


def dicom_files(slices=2):
    """Uploads in the (file, filename) form Flask's test client expects."""
    return [(BytesIO(f.getvalue()), f.filename) for f in map(make_dicom_slice, range(slices))]


def dicom_form(name="Andrei", slices=2):
    return {"name": name, "age": "30", "dicom_file": dicom_files(slices)}


def create_with_scan(client, headers):
    return client.post("/api/patients/", data=dicom_form(), headers=headers,
                       content_type="multipart/form-data")


# --- status flow -----------------------------------------------------------

def test_create_with_scan_returns_processing_then_completes(
    client, patients, files, segmenter, auth_headers
):
    response = create_with_scan(client, auth_headers)
    assert response.status_code == 201
    patient = response.get_json()["patient"]
    assert patient["status"] == "processing"

    stored = patients[patient["id"]]
    assert stored["status"] == "completed" and stored["segmented"] is True
    assert stored["metrics"]["confidence"] == 0.87
    assert set(files[patient["id"]]) == {"scan_data", "mask_data"}

    detail = client.get(f"/api/patients/{patient['id']}", headers=auth_headers).get_json()
    assert detail["patient"]["status"] == "completed"
    assert detail["patient"]["confidence"] == 0.87


def test_create_without_scan_is_pending(client, patients, auth_headers):
    response = client.post("/api/patients/", data={"name": "Ion", "age": "40"},
                           headers=auth_headers)
    assert response.get_json()["patient"]["status"] == "pending"


def test_failed_job_is_reported_with_a_message(
    client, patients, files, segmenter, auth_headers
):
    segmenter.fail_with = RuntimeError("CUDA exploded at 0x7ff")   # internal detail
    patient_id = create_with_scan(client, auth_headers).get_json()["patient"]["id"]

    detail = client.get(f"/api/patients/{patient_id}", headers=auth_headers).get_json()
    assert detail["patient"]["status"] == "failed"
    assert detail["patient"]["segmentationError"] == SEGMENTATION_FAILED   # not leaked
    assert "mask_data" not in files[patient_id]


def test_scan_rejected_before_queueing_gives_400_and_creates_nothing(
    client, patients, files, segmenter, auth_headers
):
    segmenter.reject_with = InvalidScanError("Scan too large for this server")
    count = len(patients)
    response = create_with_scan(client, auth_headers)
    assert response.status_code == 400
    assert "Scan too large" in response.get_json()["error"]
    assert len(patients) == count and segmenter.segmented == 0


def test_full_queue_gives_503_and_marks_patient_failed(
    client, patients, files, segmenter, auth_headers, monkeypatch
):
    full_queue = JobQueue(max_pending=0, inline=True)
    monkeypatch.setattr(patient_service, "_job_queue_provider", lambda: full_queue)

    response = create_with_scan(client, auth_headers)
    assert response.status_code == 503
    created = [p for p in patients.values() if p["name"] == "Andrei"][0]
    assert created["status"] == "failed"
    assert "busy" in created["segmentation_error"]
    assert "scan_data" in files[created["id"]]      # kept: the user can re-segment later


# --- upload / re-segment ---------------------------------------------------

def test_upload_replaces_the_old_mask(client, patients, files, segmenter, auth_headers):
    files["p1"] = {"mask_data": "old mask"}
    response = client.post("/api/patients/p1/upload-dicom", headers=auth_headers,
                           data={"dicom_file": dicom_files(1)},
                           content_type="multipart/form-data")
    assert response.status_code == 202
    assert response.get_json()["result"] == {"status": "processing"}
    assert files["p1"]["mask_data"].data == b"mask-bytes"          # the new one
    assert patients["p1"]["status"] == "completed"


def test_cannot_start_a_second_job_while_processing(
    client, patients, files, segmenter, auth_headers
):
    patients["p1"].update(status="processing", processing_started_at=time.time())
    upload = client.post("/api/patients/p1/upload-dicom", headers=auth_headers,
                         data={"dicom_file": dicom_files(1)},
                         content_type="multipart/form-data")
    resegment = client.post("/api/patients/p1/re-segment", headers=auth_headers)
    assert upload.status_code == resegment.status_code == 409
    assert segmenter.segmented == 0


def test_resegment_runs_the_model_on_the_stored_scan(
    client, patients, files, segmenter, auth_headers
):
    create_with_scan(client, auth_headers)
    patient_id = [p for p in patients.values() if p["name"] == "Andrei"][0]["id"]

    response = client.post(f"/api/patients/{patient_id}/re-segment", headers=auth_headers)
    assert response.status_code == 202
    assert response.get_json()["patient"]["status"] == "processing"
    assert segmenter.segmented == 2
    assert patients[patient_id]["status"] == "completed"


# --- jobs lost by a restart ------------------------------------------------

def test_stale_processing_job_is_reported_as_failed(client, patients, auth_headers):
    an_hour_ago = time.time() - 3600
    patients["p1"].update(status="processing", processing_started_at=an_hour_ago)

    detail = client.get("/api/patients/p1", headers=auth_headers).get_json()["patient"]
    assert detail["status"] == "failed"
    assert detail["segmentationError"] == PROCESSING_INTERRUPTED
    assert patients["p1"]["status"] == "failed"         # persisted, not just displayed


def test_recent_processing_job_is_left_alone(client, patients, auth_headers):
    patients["p1"].update(status="processing", processing_started_at=time.time())
    detail = client.get("/api/patients/p1", headers=auth_headers).get_json()["patient"]
    assert detail["status"] == "processing"


# --- the queue -------------------------------------------------------------

def test_queue_runs_jobs_in_the_background_one_at_a_time():
    queue = JobQueue(max_pending=5)
    release = threading.Event()
    running, max_running, done = [0], [0], []
    lock = threading.Lock()

    def job(n):
        with lock:
            running[0] += 1
            max_running[0] = max(max_running[0], running[0])
        release.wait(timeout=5)
        with lock:
            running[0] -= 1
        done.append(n)

    for n in range(3):
        queue.submit(lambda n=n: job(n))
    assert queue.pending == 3 and done == []      # submit returned immediately

    release.set()
    deadline = time.time() + 5
    while queue.pending and time.time() < deadline:
        time.sleep(0.01)
    assert done == [0, 1, 2]                      # in order
    assert max_running[0] == 1                    # never two at once


def test_queue_rejects_jobs_when_full_and_survives_crashing_jobs():
    queue = JobQueue(max_pending=1, inline=True)
    queue.submit(lambda: 1 / 0)                   # crash is logged, not raised
    assert queue.pending == 0

    blocking = JobQueue(max_pending=1)
    release = threading.Event()
    blocking.submit(lambda: release.wait(timeout=5))
    with pytest.raises(ServiceUnavailableError):
        blocking.submit(lambda: None)
    release.set()
