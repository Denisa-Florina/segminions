"""Storage for scan and mask files.

Files are kept inside Firestore as base64: small files directly on the patient document,
larger ones split into chunks in a subcollection (Firestore limits documents to 1 MB).
Callers only use `save` / `load` / `delete`, so moving to Cloud Storage later only
changes this module.
"""

import base64
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from firebase_admin import firestore

from app.extensions import get_db

logger = logging.getLogger(__name__)

SCAN = "scan_data"
MASK = "mask_data"
LEGACY = "file_data"   # written by the first version of the app
ALL_KEYS = (SCAN, MASK, LEGACY)

_PATIENTS = "patients"
_INLINE_LIMIT_BYTES = 512 * 1024
_CHUNK_SIZE = 800 * 1024


@dataclass
class StoredFile:
    data: bytes
    filename: str
    size: int


class FirestoreFileStorage:
    def _patient_ref(self, patient_id: str):
        return get_db().collection(_PATIENTS).document(patient_id)

    def _chunks_ref(self, patient_id: str, key: str):
        return self._patient_ref(patient_id).collection(f"{key}_chunks")

    def save(self, patient_id: str, stream: BytesIO, filename: str, key: str) -> None:
        stream.seek(0)
        file_bytes = stream.read()
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        size_mb = len(file_bytes) / 1024**2
        logger.info("Saving %s for patient %s (%.2f MB)", key, patient_id, size_mb)

        # Whichever format is written, the other one is removed, so `load` can never
        # return a previous version of the file.
        self._delete_chunks(patient_id, key)
        if len(file_bytes) > _INLINE_LIMIT_BYTES:
            self._save_chunks(patient_id, encoded, key)
            updates = {
                key: firestore.DELETE_FIELD,
                f"{key}_chunks_count": math.ceil(len(encoded) / _CHUNK_SIZE),
                f"{key}_is_chunked": True,
            }
        else:
            updates = {
                key: encoded,
                f"{key}_chunks_count": firestore.DELETE_FIELD,
                f"{key}_is_chunked": False,
            }

        self._patient_ref(patient_id).update({
            **updates,
            f"{key}_filename": filename,
            f"{key}_size": len(file_bytes),
            "updated_at": datetime.now(),
        })

    def load(self, patient_id: str, key: str) -> StoredFile | None:
        doc = self._patient_ref(patient_id).get()
        if not doc.exists:
            return None
        patient = doc.to_dict()

        if patient.get(f"{key}_is_chunked"):
            encoded = self._load_chunks(patient_id, key)
        elif key in patient:
            encoded = patient[key]
        else:
            return None

        return StoredFile(
            data=base64.b64decode(encoded),
            filename=patient.get(f"{key}_filename", "file.nii.gz"),
            size=patient.get(f"{key}_size", 0),
        )

    def delete(self, patient_id: str, key: str) -> None:
        """Remove one file (e.g. an outdated mask) but keep the patient document."""
        self._delete_chunks(patient_id, key)
        self._patient_ref(patient_id).update({
            field: firestore.DELETE_FIELD
            for field in (key, f"{key}_filename", f"{key}_size",
                          f"{key}_chunks_count", f"{key}_is_chunked")
        })

    def delete_all(self, patient_id: str) -> None:
        """Remove every stored file of a patient. Firestore does not delete
        subcollections together with their parent document, so the chunks must be
        deleted explicitly or the medical data would stay in the database."""
        for key in ALL_KEYS:
            self._delete_chunks(patient_id, key)

    def _save_chunks(self, patient_id: str, encoded: str, key: str) -> None:
        chunks_ref = self._chunks_ref(patient_id, key)
        for index, start in enumerate(range(0, len(encoded), _CHUNK_SIZE)):
            chunks_ref.document(f"chunk_{index}").set({
                "data": encoded[start:start + _CHUNK_SIZE],
                "order": index,
                "created_at": datetime.now(),
            })

    def _load_chunks(self, patient_id: str, key: str) -> str:
        chunks = self._chunks_ref(patient_id, key).order_by("order").stream()
        return "".join(chunk.to_dict().get("data", "") for chunk in chunks)

    def _delete_chunks(self, patient_id: str, key: str) -> None:
        for chunk in self._chunks_ref(patient_id, key).stream():
            chunk.reference.delete()
