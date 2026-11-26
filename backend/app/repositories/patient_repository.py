"""Data access for the `patients` Firestore collection (metadata only, no file contents)."""

from google.api_core.exceptions import NotFound

from app.core.clock import utc_now
from app.extensions import get_db

COLLECTION = "patients"
_FILE_FIELDS = ("file_data", "scan_data", "mask_data")
_TIMESTAMP_FIELDS = ("created_at", "updated_at")

# What the patient list needs. Fetching only these fields keeps the scan and mask
# (stored as base64 in the same document) out of every list request and every poll.
_LIST_FIELDS = (
    "name", "age", "date", "doctor_id", "filename", "dicom_file", "status", "segmented",
    "metrics", "segmentation_error", "job_id", "processing_started_at",
    "created_at", "updated_at",
)


def _to_dict(doc) -> dict:
    data = doc.to_dict()
    for field in _FILE_FIELDS:
        data.pop(field, None)
    for field in _TIMESTAMP_FIELDS:
        value = data.get(field)
        if value is not None:
            data[field] = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return {"id": doc.id, **data}


class PatientRepository:
    def _collection(self):
        return get_db().collection(COLLECTION)

    def create(self, data: dict) -> dict:
        now = utc_now()
        data = {**data, "created_at": now, "updated_at": now}
        doc_ref = self._collection().document()
        doc_ref.set(data)
        return {"id": doc_ref.id, **data}

    def list_by_doctor(self, doctor_id: str) -> list[dict]:
        query = self._collection().where("doctor_id", "==", str(doctor_id))
        docs = query.select(list(_LIST_FIELDS)).stream()
        return [_to_dict(doc) for doc in docs]

    def get(self, patient_id: str) -> dict | None:
        doc = self._collection().document(patient_id).get()
        return _to_dict(doc) if doc.exists else None

    def update(self, patient_id: str, updates: dict) -> dict | None:
        try:
            self._collection().document(patient_id).update(
                {**updates, "updated_at": utc_now()}
            )
        except NotFound:
            return None
        return self.get(patient_id)

    def delete(self, patient_id: str) -> None:
        self._collection().document(patient_id).delete()
