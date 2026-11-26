"""Regression tests for the bugs found in CODE_REVIEW.md (section 2)."""

import gzip
import time
from io import BytesIO

import nibabel as nib
import numpy as np

from app.ml.nifti_io import ensure_gzipped, is_gzipped, read_nifti, write_nifti
from app.services.patient_service import (
    RESULT_NOT_SAVED,
    SEGMENTATION_NOT_STARTED,
    patient_service,
)
from tests.conftest import LEGACY_SHA256_HASH, PASSWORD
from tests.test_segmentation_jobs import create_with_scan

VOLUME = np.arange(4 * 5 * 3, dtype=np.int16).reshape(4, 5, 3)
AFFINE = np.diag([0.5, 0.5, 2.0, 1.0])


# --- 2.1 .nii.gz files must really be gzip-compressed ------------------------

def test_written_nifti_is_gzipped_and_opens_with_nibabel(tmp_path):
    data = write_nifti(VOLUME, AFFINE).getvalue()
    assert is_gzipped(data)

    path = tmp_path / "mask.nii.gz"          # what a doctor does with a download
    path.write_bytes(data)
    loaded = nib.load(path)
    assert np.array_equal(loaded.get_fdata(), VOLUME)
    assert loaded.header.get_zooms() == (0.5, 0.5, 2.0)


def test_uncompressed_files_from_earlier_versions_are_still_readable():
    legacy = nib.Nifti1Image(VOLUME, AFFINE).to_bytes()       # no gzip
    assert np.array_equal(read_nifti(BytesIO(legacy)).get_fdata(), VOLUME)


def test_ensure_gzipped_compresses_once():
    raw = nib.Nifti1Image(VOLUME, AFFINE).to_bytes()
    once = ensure_gzipped(raw)
    assert gzip.decompress(once) == raw
    assert ensure_gzipped(once) == once                       # already gzipped: unchanged


def test_downloading_a_legacy_uncompressed_file_returns_valid_gzip(
    client, patients, files, auth_headers, tmp_path
):
    legacy = nib.Nifti1Image(VOLUME, AFFINE).to_bytes()
    patient_service.files.save("p1", BytesIO(legacy), "scan.nii.gz", "scan_data")

    response = client.get("/api/patients/p1/download/scan", headers=auth_headers)
    assert response.status_code == 200 and is_gzipped(response.data)
    path = tmp_path / "scan.nii.gz"
    path.write_bytes(response.data)
    assert np.array_equal(nib.load(path).get_fdata(), VOLUME)


# --- 2.2 no orphaned files when a patient is deleted during segmentation --------

def test_cannot_delete_a_patient_while_segmentation_runs(client, patients, auth_headers):
    patients["p1"].update(status="processing", processing_started_at=time.time())
    assert client.delete("/api/patients/p1", headers=auth_headers).status_code == 409
    assert "p1" in patients


def test_job_of_a_deleted_patient_writes_nothing(patients, files, segmenter):
    patients["p1"].update(status="processing", job_id="job-1")
    # The patient disappears while the model runs (e.g. deleted after a stale timeout).
    original_segment = segmenter.segment

    def segment_then_delete(stream):
        result = original_segment(stream)
        patients.pop("p1")
        return result

    segmenter.segment = segment_then_delete
    patient_service.run_segmentation("p1", "job-1", b"scan", "scan.nii.gz")
    assert "p1" not in files                                  # no mask written


def test_mask_written_while_the_patient_is_deleted_is_cleaned_up(
    patients, files, segmenter, monkeypatch
):
    patients["p1"].update(status="processing", job_id="job-1")
    cleaned = []

    def save_fails_because_patient_was_deleted(patient_id, stream, filename, key):
        files.setdefault(patient_id, {})[key] = "partially written chunks"
        patients.pop(patient_id)
        raise RuntimeError("404 No document to update")

    monkeypatch.setattr(patient_service.files, "save", save_fails_because_patient_was_deleted)
    monkeypatch.setattr(patient_service.files, "delete_all",
                        lambda patient_id: cleaned.append(files.pop(patient_id, None)))
    patient_service.run_segmentation("p1", "job-1", b"scan", "scan.nii.gz")
    assert cleaned and "p1" not in files


def test_failed_mask_save_marks_the_patient_failed(patients, files, segmenter, monkeypatch):
    patients["p1"].update(status="processing", job_id="job-1")

    def save_fails(*args):
        raise RuntimeError("Firestore unavailable")

    monkeypatch.setattr(patient_service.files, "save", save_fails)
    patient_service.run_segmentation("p1", "job-1", b"scan", "scan.nii.gz")
    assert patients["p1"]["status"] == "failed"
    assert patients["p1"]["segmentation_error"] == RESULT_NOT_SAVED


# --- 2.3 a superseded job never overwrites a newer result ------------------------

def test_superseded_job_does_not_overwrite_the_newer_scan(patients, files, segmenter):
    # Job "old" was marked stale, then the doctor uploaded a new scan (job "new").
    patients["p1"].update(status="processing", job_id="new", metrics={})
    patient_service.run_segmentation("p1", "old", b"old scan", "old.nii.gz")

    assert patients["p1"]["status"] == "processing"            # untouched
    assert patients["p1"]["metrics"] == {}
    assert "mask_data" not in files.get("p1", {})


def test_superseded_job_failure_is_not_recorded(patients, files, segmenter):
    patients["p1"].update(status="processing", job_id="new")
    segmenter.fail_with = RuntimeError("boom")
    patient_service.run_segmentation("p1", "old", b"old scan", "old.nii.gz")
    assert patients["p1"]["status"] == "processing"


def test_each_job_start_records_a_new_job_id(client, patients, files, segmenter, auth_headers):
    create_with_scan(client, auth_headers)
    patient_id = [p for p in patients.values() if p["name"] == "Andrei"][0]["id"]
    first = patients[patient_id]["job_id"]
    client.post(f"/api/patients/{patient_id}/re-segment", headers=auth_headers)
    second = patients[patient_id]["job_id"]
    assert first and second and first != second
    assert patients[patient_id]["status"] == "completed"        # the current job wrote it


# --- 2.4 email login is case-insensitive ---------------------------------------

def login(client, email, password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_ignores_email_case_and_surrounding_spaces(client, doctors):
    assert login(client, "  Doctor@Example.COM ").status_code == 200


def test_legacy_mixed_case_email_is_normalised_on_first_login(client, doctors):
    doctors["doctor-2"] = {"id": "doctor-2", "email": "Ana.Pop@Spital.ro",
                           "name": "Dr. Pop", "password": LEGACY_SHA256_HASH}

    assert login(client, "Ana.Pop@Spital.ro").status_code == 200    # as stored
    assert doctors["doctor-2"]["email"] == "ana.pop@spital.ro"       # normalised
    assert login(client, "ANA.POP@spital.ro").status_code == 200    # any case from now on


# --- 2.5 internal error text never reaches users ---------------------------------

def test_unexpected_enqueue_error_stores_a_generic_message(
    client, patients, files, segmenter, auth_headers, monkeypatch
):
    def broken_queue():
        raise RuntimeError("Job queue is not initialised. Call init_job_queue() first.")

    monkeypatch.setattr(patient_service, "_job_queue_provider", broken_queue)
    response = create_with_scan(client, auth_headers)
    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error"}
    created = [p for p in patients.values() if p["name"] == "Andrei"][0]
    assert created["segmentation_error"] == SEGMENTATION_NOT_STARTED
