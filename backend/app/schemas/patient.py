"""Input validation and output serialisation for patients."""

from app.core.errors import ValidationError

MIN_AGE, MAX_AGE = 1, 150
EDITABLE_FIELDS = {"name", "age"}


def to_patient_summary(patient: dict, unsegmented_status: str = "processing") -> dict:
    return {
        "id": patient["id"],
        "name": patient["name"],
        "age": patient["age"],
        "date": patient["date"],
        "dicomFile": patient.get("dicom_file", ""),
        "status": "completed" if patient.get("segmented") else unsegmented_status,
        "confidence": patient.get("metrics", {}).get("confidence", 0),
    }


def to_patient_detail(patient: dict) -> dict:
    return {**to_patient_summary(patient), "metrics": patient.get("metrics", {})}


def parse_age(raw_age) -> int:
    try:
        age = int(raw_age)
    except (TypeError, ValueError):
        raise ValidationError("Age must be a valid number") from None
    if not MIN_AGE <= age <= MAX_AGE:
        raise ValidationError(f"Age must be between {MIN_AGE} and {MAX_AGE}")
    return age


def parse_new_patient(form, doctor_id: str | None) -> tuple[str, int, str]:
    name = form.get("name")
    raw_age = form.get("age")
    if not name or not raw_age or not doctor_id:
        raise ValidationError("Name, age, and doctor_id are required")
    return name, parse_age(raw_age), doctor_id


def parse_patient_updates(data: dict | None) -> dict:
    if not data:
        raise ValidationError("No data provided")
    return {key: value for key, value in data.items() if key in EDITABLE_FIELDS}
