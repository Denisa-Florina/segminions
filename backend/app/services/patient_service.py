"""Patient workflows: create, upload scans, run segmentation, download results."""

import io
import logging
import zipfile
from datetime import datetime

from app.core.errors import NotFoundError, ValidationError
from app.extensions import get_segmenter
from app.ml.dicom_converter import DicomConversionError, NiftiScan, convert_dicom_series
from app.repositories.patient_repository import PatientRepository
from app.storage.file_storage import MASK, SCAN, FirestoreFileStorage, StoredFile

logger = logging.getLogger(__name__)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _mask_filename(scan_filename: str) -> str:
    return scan_filename.replace(".nii.gz", "_mask.nii.gz")


class PatientService:
    def __init__(
        self, patients: PatientRepository, files: FirestoreFileStorage, segmenter_provider
    ):
        self.patients = patients
        self.files = files
        self._segmenter_provider = segmenter_provider

    # --- queries -----------------------------------------------------------

    def list_for_doctor(self, doctor_id: str) -> list[dict]:
        return self.patients.list_by_doctor(doctor_id)

    def get(self, patient_id: str) -> dict:
        patient = self.patients.get(patient_id)
        if not patient:
            raise NotFoundError("Patient not found")
        return patient

    def get_file(self, patient_id: str, key: str, not_found_message: str) -> StoredFile:
        stored = self.files.load(patient_id, key)
        if not stored:
            raise NotFoundError(not_found_message)
        return stored

    def build_results_zip(self, patient_id: str) -> tuple[io.BytesIO, str]:
        scan = self.get_file(patient_id, SCAN, "Scan file not found")
        mask = self.get_file(patient_id, MASK, "Mask file not found")

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(scan.filename or "scan.nii.gz", scan.data)
            archive.writestr(mask.filename or "mask.nii.gz", mask.data)
        buffer.seek(0)

        patient_name = self.get(patient_id).get("name", "patient").replace(" ", "_")
        return buffer, f"{patient_name}_segmentation_results.zip"

    # --- commands ----------------------------------------------------------

    def create(self, name: str, age: int, doctor_id: str, dicom_files) -> dict:
        base = {"name": name, "age": age, "doctor_id": str(doctor_id), "date": _today()}

        if not dicom_files:
            return self.patients.create({**base, "segmented": False, "metrics": {"confidence": 0}})

        scan = self._convert(dicom_files)
        metrics, mask_stream = self._segmenter_provider().segment(scan.stream)

        patient = self.patients.create({
            **base,
            "filename": scan.filename,
            "file_size": scan.size,
            "segmented": True,
            "metrics": metrics,
        })
        try:
            self._store_results(patient["id"], scan, mask_stream)
        except Exception:
            logger.exception("Patient %s created but its files could not be saved", patient["id"])
        return patient

    def upload_scan(self, patient_id: str, dicom_files) -> dict:
        if not dicom_files:
            raise ValidationError("No DICOM file uploaded")
        self.get(patient_id)

        scan = self._convert(dicom_files)
        metrics, mask_stream = self._segmenter_provider().segment(scan.stream)
        self._store_results(patient_id, scan, mask_stream)

        date = _today()
        self.patients.update(patient_id, {
            "filename": scan.filename,
            "file_size": scan.size,
            "metrics": metrics,
            "segmented": True,
            "date": date,
        })
        return {
            "success": True,
            "confidence": metrics["confidence"],
            "segmentationComplete": True,
            "date": date,
            "metrics": metrics,
        }

    def resegment(self, patient_id: str) -> dict:
        patient = self.get(patient_id)
        scan = self.get_file(patient_id, SCAN, "Scan file not found")

        metrics, mask_stream = self._segmenter_provider().segment(io.BytesIO(scan.data))
        self.files.save(
            patient_id, mask_stream, _mask_filename(patient.get("filename", "scan.nii.gz")), MASK
        )
        return self.patients.update(patient_id, {"metrics": metrics})

    def update(self, patient_id: str, updates: dict) -> dict:
        patient = self.patients.update(patient_id, updates)
        if not patient:
            raise NotFoundError("Patient not found")
        return patient

    def delete(self, patient_id: str) -> None:
        self.get(patient_id)
        self.patients.delete(patient_id)

    # --- helpers -----------------------------------------------------------

    @staticmethod
    def _convert(dicom_files) -> NiftiScan:
        try:
            return convert_dicom_series(dicom_files)
        except DicomConversionError as error:
            raise ValidationError(str(error)) from error

    def _store_results(self, patient_id: str, scan: NiftiScan, mask_stream) -> None:
        self.files.save(patient_id, scan.stream, scan.filename, SCAN)
        self.files.save(patient_id, mask_stream, _mask_filename(scan.filename), MASK)


patient_service = PatientService(PatientRepository(), FirestoreFileStorage(), get_segmenter)
