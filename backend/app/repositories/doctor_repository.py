"""Data access for the `doctors` Firestore collection."""

from app.extensions import get_db

COLLECTION = "doctors"


class DoctorRepository:
    def _collection(self):
        return get_db().collection(COLLECTION)

    def get_by_email(self, email: str) -> dict | None:
        docs = self._collection().where("email", "==", email).limit(1).stream()
        for doc in docs:
            return {"id": doc.id, **doc.to_dict()}
        return None

    def get_by_id(self, doctor_id: str) -> dict | None:
        doc = self._collection().document(doctor_id).get()
        if not doc.exists:
            return None
        return {"id": doc.id, **doc.to_dict()}

    def update_password_hash(self, doctor_id: str, password_hash: str) -> None:
        self._collection().document(doctor_id).update({"password": password_hash})

    def update_email(self, doctor_id: str, email: str) -> None:
        self._collection().document(doctor_id).update({"email": email})
