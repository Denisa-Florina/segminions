"""Shared resources initialised once per process: the Firestore client and the AI model."""

import json
import logging

import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

_db = None
_segmenter = None


def init_firebase(app) -> None:
    global _db
    if not firebase_admin._apps:
        raw_json = app.config["FIREBASE_SERVICE_ACCOUNT_JSON"]
        if raw_json:
            cred = credentials.Certificate(json.loads(raw_json))
        else:
            cred = credentials.Certificate(str(app.config["FIREBASE_CREDENTIALS_PATH"]))
        firebase_admin.initialize_app(cred)
    _db = firestore.client()
    logger.info("Firestore client initialised")


def init_segmenter(app) -> None:
    global _segmenter
    # Imported here so that torch is only loaded when the model is actually needed.
    from app.ml.inference import Segmenter

    _segmenter = Segmenter(
        app.config["MODEL_DIR"],
        num_threads=app.config["TORCH_NUM_THREADS"],
        batch_size=app.config["INFERENCE_BATCH_SIZE"],
    )


def get_db():
    if _db is None:
        raise RuntimeError("Firestore is not initialised. Call init_firebase() first.")
    return _db


def get_segmenter():
    if _segmenter is None:
        raise RuntimeError("Segmenter is not initialised. Call init_segmenter() first.")
    return _segmenter
