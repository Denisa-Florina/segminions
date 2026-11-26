"""Patient workflows: create, upload scans, run segmentation, download results.

Every operation is scoped to the authenticated doctor: a patient that belongs to
another doctor is reported as not found, so its existence is not revealed.

Segmentation runs in the background. A request validates and stores the scan, marks
the patient `processing` and returns; the job then sets `completed` (with metrics and
mask) or `failed` (with a message). Status flow:

    pending (no scan) -> processing -> completed | failed -> processing (re-segment) ...

Each job gets an id, stored on the patient when it is queued. A job only writes its
result while it is still the patient's current job, so a late job can never overwrite
the result of a newer scan, and a job whose patient was deleted cleans up after itself.
"""

import io
import logging
import time
import uuid
import zipfile
from datetime import timedelta

from flask import current_app

from app.core.clock import Clock, as_utc, utc_now
from app.core.errors import AppError, ConflictError, NotFoundError, ValidationError
from app.extensions import get_job_queue, get_segmenter
from app.ml.dicom_converter import DicomConversionError, NiftiScan, convert_dicom_series
from app.ml.errors import InvalidScanError
from app.ml.nifti_io import ensure_gzipped
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import PatientCreate
from app.storage.file_storage import MASK, SCAN, FirestoreFileStorage, StoredFile

logger = logging.getLogger(__name__)

PENDING, PROCESSING, COMPLETED, FAILED = "pending", "processing", "completed", "failed"

SEGMENTATION_FAILED = "Segmentation failed. Please try again or upload a different scan."
SEGMENTATION_NOT_STARTED = "Segmentation could not be started. Please try again."
RESULT_NOT_SAVED = "The segmentation result could not be saved. Please re-segment."
PROCESSING_INTERRUPTED = "Processing was interrupted (server restart). Please re-segment."


def _mask_filename(scan_filename: str) -> str:
    return scan_filename.replace(".nii.gz", "_mask.nii.gz")


def _new_job_id() -> str:
    return uuid.uuid4().hex


class PatientService:
    def __init__(
        self,
        patients: PatientRepository,
        files: FirestoreFileStorage,
        segmenter_provider,
        job_queue_provider,
        clock: Clock = utc_now,
    ):
        self.patients = patients
        self.files = files
        self._segmenter_provider = segmenter_provider
        self._job_queue_provider = job_queue_provider
        self._clock = clock

    # --- queries -----------------------------------------------------------

    def list_for_doctor(self, doctor_id: str) -> list[dict]:
        return [self._expire_if_stale(p) for p in self.patients.list_by_doctor(doctor_id)]

    def get(self, patient_id: str, doctor_id: str) -> dict:
        patient = self.patients.get(patient_id)
        if not patient or patient.get("doctor_id") != str(doctor_id):
            raise NotFoundError("Patient not found")
        return self._expire_if_stale(patient)

    def get_file(
        self, patient_id: str, doctor_id: str, key: str, not_found_message: str
    ) -> StoredFile:
        self.get(patient_id, doctor_id)
        stored = self.files.load(patient_id, key)
        if not stored:
            raise NotFoundError(not_found_message)
        return stored

    def build_results_zip(self, patient_id: str, doctor_id: str) -> tuple[io.BytesIO, str]:
        patient = self.get(patient_id, doctor_id)
        scan = self.get_file(patient_id, doctor_id, SCAN, "Scan file not found")
        mask = self.get_file(patient_id, doctor_id, MASK, "Mask file not found")

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(scan.filename or "scan.nii.gz", ensure_gzipped(scan.data))
            archive.writestr(mask.filename or "mask.nii.gz", ensure_gzipped(mask.data))
        buffer.seek(0)

        patient_name = patient.get("name", "patient").replace(" ", "_")
        return buffer, f"{patient_name}_segmentation_results.zip"

    # --- commands ----------------------------------------------------------

    def create(self, data: PatientCreate, dicom_files) -> dict:
        base = {**data.model_dump(), "date": self._today(), "segmented": False, "metrics": {}}
        if not dicom_files:
            return self.patients.create({**base, "status": PENDING})

        scan = self._prepare_scan(dicom_files)
        job_id = _new_job_id()
        patient = self.patients.create({
            **base, **self._processing_fields(job_id),
            "filename": scan.filename, "file_size": scan.size,
        })
        self._store_scan_and_enqueue(patient["id"], job_id, scan)
        return patient

    def upload_scan(self, patient_id: str, doctor_id: str, dicom_files) -> dict:
        if not dicom_files:
            raise ValidationError("No DICOM file uploaded")
        self._ensure_not_processing(self.get(patient_id, doctor_id))

        scan = self._prepare_scan(dicom_files)
        job_id = _new_job_id()
        # The previous mask belongs to the previous scan: never serve it for the new one.
        self.files.delete(patient_id, MASK)
        self.patients.update(patient_id, {
            **self._processing_fields(job_id), "segmented": False, "metrics": {},
            "filename": scan.filename, "file_size": scan.size,
        })
        self._store_scan_and_enqueue(patient_id, job_id, scan)
        return {"status": PROCESSING}

    def resegment(self, patient_id: str, doctor_id: str) -> dict:
        patient = self.get(patient_id, doctor_id)
        self._ensure_not_processing(patient)
        scan = self.get_file(patient_id, doctor_id, SCAN, "Scan file not found")
        self._check_scan(io.BytesIO(scan.data))

        job_id = _new_job_id()
        updated = self.patients.update(patient_id, self._processing_fields(job_id))
        self._enqueue(patient_id, job_id, scan.data, patient.get("filename") or "scan.nii.gz")
        return updated

    def update(self, patient_id: str, doctor_id: str, updates: dict) -> dict:
        self.get(patient_id, doctor_id)
        patient = self.patients.update(patient_id, updates)
        if not patient:
            raise NotFoundError("Patient not found")
        return patient

    def delete(self, patient_id: str, doctor_id: str) -> None:
        patient = self.get(patient_id, doctor_id)
        if patient.get("status") == PROCESSING:
            # The running job would write its mask under a deleted patient.
            raise ConflictError("Cannot delete a patient while segmentation is in progress")
        self.files.delete_all(patient_id)
        self.patients.delete(patient_id)

    # --- background job ----------------------------------------------------

    def run_segmentation(
        self, patient_id: str, job_id: str, scan_bytes: bytes, scan_filename: str
    ) -> None:
        """The background job. Records its outcome on the patient; never raises."""
        started = time.perf_counter()
        try:
            metrics, mask_stream = self._segmenter_provider().segment(io.BytesIO(scan_bytes))
        except Exception as error:
            logger.exception("Segmentation failed for patient %s", patient_id)
            message = str(error) if isinstance(error, InvalidScanError) else SEGMENTATION_FAILED
            self._finish_job(patient_id, job_id, {"status": FAILED, "segmentation_error": message})
            return

        if not self._is_current_job(patient_id, job_id):
            return
        try:
            self.files.save(patient_id, mask_stream, _mask_filename(scan_filename), MASK)
        except Exception:
            logger.exception("Could not save the mask of patient %s", patient_id)
            if self.patients.get(patient_id) is None:
                # Deleted while the mask was being written: remove what was written.
                self.files.delete_all(patient_id)
            else:
                self._finish_job(
                    patient_id, job_id, {"status": FAILED, "segmentation_error": RESULT_NOT_SAVED}
                )
            return

        self._finish_job(patient_id, job_id, {
            "status": COMPLETED, "segmented": True, "metrics": metrics,
            "segmentation_error": None, "date": self._today(),
        })
        logger.info("Patient %s segmented in %.1fs", patient_id, time.perf_counter() - started)

    def _is_current_job(self, patient_id: str, job_id: str) -> bool:
        patient = self.patients.get(patient_id)
        if patient is None:
            logger.info("Discarding job %s: patient %s no longer exists", job_id, patient_id)
            return False
        if patient.get("job_id") != job_id:
            logger.info("Discarding job %s: superseded by a newer job", job_id)
            return False
        return True

    def _finish_job(self, patient_id: str, job_id: str, changes: dict) -> None:
        if self._is_current_job(patient_id, job_id):
            self.patients.update(patient_id, changes)

    # --- helpers -----------------------------------------------------------

    def _prepare_scan(self, dicom_files) -> NiftiScan:
        """Convert and validate in the request, so bad uploads fail immediately."""
        max_files = current_app.config["MAX_DICOM_FILES"]
        if len(dicom_files) > max_files:
            raise ValidationError(f"Too many files: at most {max_files} DICOM slices per upload")
        try:
            scan = convert_dicom_series(dicom_files)
        except DicomConversionError as error:
            raise ValidationError(str(error)) from error
        self._check_scan(scan.stream)
        return scan

    def _check_scan(self, stream: io.BytesIO) -> None:
        try:
            self._segmenter_provider().check_scan(stream)
        except InvalidScanError as error:
            raise ValidationError(str(error)) from error

    def _store_scan_and_enqueue(self, patient_id: str, job_id: str, scan: NiftiScan) -> None:
        try:
            self.files.save(patient_id, scan.stream, scan.filename, SCAN)
        except Exception:
            self._mark_failed(patient_id, "The scan could not be saved.")
            raise
        self._enqueue(patient_id, job_id, scan.stream.getvalue(), scan.filename)

    def _enqueue(
        self, patient_id: str, job_id: str, scan_bytes: bytes, scan_filename: str
    ) -> None:
        try:
            self._job_queue_provider().submit(
                lambda: self.run_segmentation(patient_id, job_id, scan_bytes, scan_filename)
            )
        except Exception as error:
            # e.g. the queue is full: the scan is stored, the user can re-segment later.
            # Only our own messages are shown to users, never internal exception text.
            message = error.message if isinstance(error, AppError) else SEGMENTATION_NOT_STARTED
            self._mark_failed(patient_id, message)
            raise

    def _today(self) -> str:
        return self._clock().strftime("%Y-%m-%d")

    def _processing_fields(self, job_id: str) -> dict:
        return {"status": PROCESSING, "job_id": job_id,
                "processing_started_at": self._clock(), "segmentation_error": None}

    def _mark_failed(self, patient_id: str, message: str) -> None:
        self.patients.update(patient_id, {"status": FAILED, "segmentation_error": message})

    @staticmethod
    def _ensure_not_processing(patient: dict) -> None:
        if patient.get("status") == PROCESSING:
            raise ConflictError("Segmentation is already in progress for this patient")

    def _expire_if_stale(self, patient: dict) -> dict:
        """A job still `processing` long after it started was lost (e.g. the server
        restarted): report it as failed instead of leaving it spinning forever."""
        started = as_utc(patient.get("processing_started_at"))
        if patient.get("status") != PROCESSING or not started:
            return patient
        stale_after = timedelta(minutes=current_app.config["JOB_STALE_AFTER_MINUTES"])
        if self._clock() - started < stale_after:
            return patient
        logger.warning("Marking stale segmentation job of patient %s as failed", patient["id"])
        self._mark_failed(patient["id"], PROCESSING_INTERRUPTED)
        return {**patient, "status": FAILED, "segmentation_error": PROCESSING_INTERRUPTED}


patient_service = PatientService(
    PatientRepository(), FirestoreFileStorage(), get_segmenter, get_job_queue
)
