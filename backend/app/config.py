"""Application configuration, read from environment variables."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB per request
    MAX_DICOM_FILES = 1000  # slices per upload
    ACCESS_TOKEN_TTL_MINUTES = int(os.environ.get("ACCESS_TOKEN_TTL_MINUTES", 8 * 60))

    FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://medsegai.web.app").rstrip("/")
    CORS_ORIGINS = ["http://localhost:3000", "http://localhost:3001", FRONTEND_URL]

    # Either the full service-account JSON (used on Render) or a path to the key file.
    FIREBASE_SERVICE_ACCOUNT_JSON = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    FIREBASE_CREDENTIALS_PATH = Path(
        os.environ.get("FIREBASE_CREDENTIALS_PATH", BASE_DIR / "serviceAccountKey.json")
    )

    MODEL_DIR = Path(os.environ.get("MODEL_DIR", BASE_DIR / "ml_weights" / "nnunet"))
    # PyTorch defaults to one thread per host core, which thrashes on small container
    # CPU quotas (Render free tier: 0.1 CPU). Raise this on machines with dedicated cores.
    TORCH_NUM_THREADS = int(os.environ.get("TORCH_NUM_THREADS", 1))
    # Slices per forward pass. On CPU, larger batches only raise peak memory
    # (measured: +110 MB at 16 vs +8 MB at 1, same speed); raise it on a GPU.
    INFERENCE_BATCH_SIZE = int(os.environ.get("INFERENCE_BATCH_SIZE", 1))

    INIT_FIREBASE = True
    LOAD_MODEL = True
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key")


class ProductionConfig(Config):
    pass


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    INIT_FIREBASE = False
    LOAD_MODEL = False


_CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config() -> type[Config]:
    env = os.environ.get("APP_ENV") or os.environ.get("FLASK_ENV") or "production"
    try:
        return _CONFIGS[env]
    except KeyError:
        raise RuntimeError(
            f"Unknown APP_ENV '{env}'. Expected one of: {', '.join(_CONFIGS)}"
        ) from None
