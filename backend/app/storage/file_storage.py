"""Storage for scan and mask files.

Files are currently kept inside Firestore as base64: small files directly on the
patient document, larger ones split into chunks in a subcollection (Firestore limits
documents to 1 MB). Callers only use `save` / `load`, so moving to Cloud Storage
later only changes this module.
"""

import base64
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from app.extensions import get_db

logger = logging.getLogger(__name__)

SCAN = "scan_data"
MASK = "mask_data"

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

    def save(self, patient_id: str, stream: BytesIO, filename: str, key: str) -> None:
        stream.seek(0)
        file_bytes = stream.read()
        encoded = base64.b64encode(file_bytes).decode("utf-8")
        size_mb = len(file_bytes) / 1024**2
        logger.info("Saving %s for patient %s (%.2f MB)", key, patient_id, size_mb)

        if len(file_bytes) > _INLINE_LIMIT_BYTES:
            self._save_chunked(patient_id, encoded, key)
            updates = {
                f"{key}_chunks_count": math.ceil(len(encoded) / _CHUNK_SIZE),
                f"{key}_is_chunked": True,
            }
        else:
            updates = {key: encoded}

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
            encoded = self._load_chunked(patient_id, key)
        elif key in patient:
            encoded = patient[key]
        else:
            return None

        return StoredFile(
            data=base64.b64decode(encoded),
            filename=patient.get(f"{key}_filename", "file.nii.gz"),
            size=patient.get(f"{key}_size", 0),
        )

    def _chunks_ref(self, patient_id: str, key: str):
        return self._patient_ref(patient_id).collection(f"{key}_chunks")

    def _save_chunked(self, patient_id: str, encoded: str, key: str) -> None:
        chunks_ref = self._chunks_ref(patient_id, key)
        for old_chunk in chunks_ref.stream():
            old_chunk.reference.delete()

        for index, start in enumerate(range(0, len(encoded), _CHUNK_SIZE)):
            chunks_ref.document(f"chunk_{index}").set({
                "data": encoded[start:start + _CHUNK_SIZE],
                "order": index,
                "created_at": datetime.now(),
            })

    def _load_chunked(self, patient_id: str, key: str) -> str:
        chunks = self._chunks_ref(patient_id, key).order_by("order").stream()
        return "".join(chunk.to_dict().get("data", "") for chunk in chunks)
