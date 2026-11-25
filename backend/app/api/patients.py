import io

from flask import Blueprint, jsonify, request, send_file

from app.core.errors import ValidationError
from app.core.security import current_doctor_id
from app.schemas.patient import (
    PatientCreate,
    PatientDetail,
    PatientSummary,
    PatientUpdate,
    validate_input,
)
from app.services.patient_service import patient_service
from app.storage.file_storage import MASK, SCAN

patients_bp = Blueprint("patients", __name__, url_prefix="/api/patients")


@patients_bp.get("/", strict_slashes=False)
def list_patients():
    doctor_id = current_doctor_id()
    if not doctor_id:
        raise ValidationError("doctor_id is required")
    patients = patient_service.list_for_doctor(doctor_id)
    return jsonify({"patients": [PatientSummary.from_db(p).to_json() for p in patients]}), 200


@patients_bp.get("/<patient_id>")
def get_patient(patient_id):
    patient = patient_service.get(patient_id)
    return jsonify({"patient": PatientDetail.from_db(patient).to_json()}), 200


@patients_bp.post("/", strict_slashes=False)
def create_patient():
    form = request.form.to_dict()
    doctor_id = current_doctor_id()
    if doctor_id:
        form["doctor_id"] = doctor_id
    data = validate_input(PatientCreate, form)

    patient = patient_service.create(data, request.files.getlist("dicom_file"))
    return jsonify({
        "message": "Patient created successfully",
        "patient": PatientSummary.from_db(patient, unsegmented_status="pending").to_json(),
    }), 201


@patients_bp.post("/<patient_id>/upload-dicom")
def upload_dicom(patient_id):
    result = patient_service.upload_scan(patient_id, request.files.getlist("dicom_file"))
    return jsonify({"message": "DICOM uploaded and processed successfully", "result": result}), 200


@patients_bp.put("/<patient_id>")
def update_patient(patient_id):
    body = request.get_json(silent=True)
    if not body:
        raise ValidationError("No data provided")
    updates = validate_input(PatientUpdate, body)

    changes = updates.model_dump(exclude_unset=True, exclude_none=True)
    patient = patient_service.update(patient_id, changes)
    return jsonify({"message": "Patient updated successfully", "patient": patient}), 200


@patients_bp.delete("/<patient_id>")
def delete_patient(patient_id):
    patient_service.delete(patient_id)
    return jsonify({"message": "Patient deleted successfully"}), 200


@patients_bp.post("/<patient_id>/re-segment")
def resegment_patient(patient_id):
    patient = patient_service.resegment(patient_id)
    return jsonify({"message": "Re-segmentation completed", "patient": patient}), 200


@patients_bp.get("/<patient_id>/download/scan")
@patients_bp.get("/<patient_id>/download")
def download_scan(patient_id):
    stored = patient_service.get_file(patient_id, SCAN, "Scan file not found")
    return _send_gzip(stored.data, stored.filename or "scan.nii.gz")


@patients_bp.get("/<patient_id>/download/mask")
def download_mask(patient_id):
    stored = patient_service.get_file(patient_id, MASK, "Segmentation mask not found")
    return _send_gzip(stored.data, stored.filename or "segmentation_mask.nii.gz")


@patients_bp.get("/<patient_id>/download/both")
def download_both(patient_id):
    buffer, filename = patient_service.build_results_zip(patient_id)
    return send_file(buffer, mimetype="application/zip", as_attachment=True, download_name=filename)


def _send_gzip(data: bytes, filename: str):
    return send_file(
        io.BytesIO(data), mimetype="application/gzip", as_attachment=True, download_name=filename
    )
