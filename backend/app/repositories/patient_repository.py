"""Data access for the `patients` Firestore collection (metadata only, no file contents)."""

from datetime import datetime

from google.api_core.exceptions import NotFound

from app.extensions import get_db

COLLECTION = "patients"
_FILE_FIELDS = ("file_data", "scan_data", "mask_data")
_TIMESTAMP_FIELDS = ("created_at", "updated_at")


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
        now = datetime.now()
        data = {**data, "created_at": now, "updated_at": now}
        doc_ref = self._collection().document()
        doc_ref.set(data)
        return {"id": doc_ref.id, **data}

    def list_by_doctor(self, doctor_id: str) -> list[dict]:
        docs = self._collection().where("doctor_id", "==", str(doctor_id)).stream()
        return [_to_dict(doc) for doc in docs]

    def get(self, patient_id: str) -> dict | None:
        doc = self._collection().document(patient_id).get()
        return _to_dict(doc) if doc.exists else None

    def update(self, patient_id: str, updates: dict) -> dict | None:
        try:
            self._collection().document(patient_id).update(
                {**updates, "updated_at": datetime.now()}
            )
        except NotFound:
            return None
        return self.get(patient_id)

    def delete(self, patient_id: str) -> None:
        self._collection().document(patient_id).delete()
