"""Background segmentation: status flow, failures, job ownership, and the job queue.

TestingConfig runs jobs inline, so a job has finished when the request returns; the
response still shows the state at the moment the job was queued."""

import threading
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO

from app.core.clock import utc_now
from app.core.job_queue import JobQueue
from app.services.patient_service import (
    PROCESSING_INTERRUPTED,
    SEGMENTATION_FAILED,
    patient_service,
)
from tests.test_dicom_converter import make_dicom_slice


def dicom_files(slices=2):
    """Uploads in the (file, filename) form Flask's test client expects."""
    return [(BytesIO(f.getvalue()), f.filename) for f in map(make_dicom_slice, range(slices))]


def create_with_scan(client, headers):
    return client.post("/api/patients/", headers=headers, content_type="multipart/form-data",
                       data={"name": "Andrei", "age": "30", "dicom_file": dicom_files()})


# --- status flow -----------------------------------------------------------

def test_create_with_scan_returns_processing_then_completes(
    client, patients, files, segmenter, auth_headers
):
    response = create_with_scan(client, auth_headers)
    assert response.status_code == 201
    patient = response.get_json()["patient"]
    assert patient["status"] == "processing"

    detail = client.get(f"/api/patients/{patient['id']}", headers=auth_headers).get_json()
    assert detail["patient"]["status"] == "completed"
    assert detail["patient"]["confidence"] == 0.87
    assert set(files[patient["id"]]) == {"scan_data", "mask_data"}


def test_failed_job_is_reported_without_leaking_internal_details(
    client, patients, files, segmenter, auth_headers
):
    segmenter.fail_with = RuntimeError("CUDA exploded at 0x7ff")
    patient_id = create_with_scan(client, auth_headers).get_json()["patient"]["id"]

    detail = client.get(f"/api/patients/{patient_id}", headers=auth_headers).get_json()
    assert detail["patient"]["status"] == "failed"
    assert detail["patient"]["segmentationError"] == SEGMENTATION_FAILED
    assert "mask_data" not in files[patient_id]


def test_full_queue_gives_503_and_keeps_the_scan(
    client, patients, files, segmenter, auth_headers, monkeypatch
):
    full_queue = JobQueue(max_pending=0, inline=True)
    monkeypatch.setattr(patient_service, "_job_queue_provider", lambda: full_queue)

    assert create_with_scan(client, auth_headers).status_code == 503
    created = [p for p in patients.values() if p["name"] == "Andrei"][0]
    assert created["status"] == "failed"
    assert "scan_data" in files[created["id"]]      # kept: the user can re-segment later


def test_cannot_start_a_second_job_while_processing(
    client, patients, files, segmenter, auth_headers
):
    patients["p1"].update(status="processing", processing_started_at=utc_now())
    response = client.post("/api/patients/p1/re-segment", headers=auth_headers)
    assert response.status_code == 409
    assert segmenter.segmented == 0


# --- a job only writes while it is the patient's current job --------------------

def test_superseded_job_does_not_overwrite_the_newer_scan(patients, files, segmenter):
    # Job "old" was marked stale, then the doctor uploaded a new scan (job "new").
    patients["p1"].update(status="processing", job_id="new", metrics={})
    patient_service.run_segmentation("p1", "old", b"old scan", "old.nii.gz")

    assert patients["p1"]["status"] == "processing"            # untouched
    assert "mask_data" not in files.get("p1", {})


def test_job_of_a_deleted_patient_writes_nothing(patients, files, segmenter):
    patients["p1"].update(status="processing", job_id="job-1")
    original_segment = segmenter.segment

    def segment_then_delete(stream):                 # deleted while the model runs
        result = original_segment(stream)
        patients.pop("p1")
        return result

    segmenter.segment = segment_then_delete
    patient_service.run_segmentation("p1", "job-1", b"scan", "scan.nii.gz")
    assert "p1" not in files                         # no orphaned mask


def test_job_lost_by_a_restart_is_reported_as_failed(client, patients, auth_headers, monkeypatch):
    started = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    patients["p1"].update(status="processing", processing_started_at=started)

    monkeypatch.setattr(patient_service, "_clock", lambda: started + timedelta(minutes=19))
    detail = client.get("/api/patients/p1", headers=auth_headers).get_json()["patient"]
    assert detail["status"] == "processing"

    monkeypatch.setattr(patient_service, "_clock", lambda: started + timedelta(minutes=21))
    detail = client.get("/api/patients/p1", headers=auth_headers).get_json()["patient"]
    assert detail["status"] == "failed"
    assert detail["segmentationError"] == PROCESSING_INTERRUPTED


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
