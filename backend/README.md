# MedSeg AI – Backend

Flask API for MedSeg AI: doctors manage patients, upload CT scans (DICOM) and receive an
AI segmentation mask produced by an nnU-Net 2D model.

## Architecture

```
backend/
├── app/
│   ├── __init__.py        # create_app() – application factory
│   ├── config.py          # configuration from environment variables
│   ├── extensions.py      # Firestore client and AI model, initialised once per process
│   ├── api/               # HTTP layer: request parsing and responses only
│   ├── core/              # error handling, request identity
│   ├── schemas/           # input validation and JSON serialisation
│   ├── services/          # business logic
│   ├── repositories/      # Firestore data access
│   ├── storage/           # scan / mask file storage
│   └── ml/                # DICOM conversion, preprocessing, model, inference (no Flask)
├── ml_weights/nnunet/     # trained model: checkpoint, plans.json, dataset.json
├── tests/
└── wsgi.py                # entry point
```

Requests flow in one direction: `api → services → repositories / storage / ml`.
The `ml` package does not depend on Flask or Firebase and can be tested on its own.

## Running locally

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env              # then fill in SECRET_KEY and the Firebase credentials
python wsgi.py                    # http://127.0.0.1:5001/api/health
```

## Tests and linting

```bash
pytest
ruff check .
```

The tests use `TestingConfig`, which skips Firebase and the AI model, so they run without
credentials or GPU.

## Deployment (Render)

- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn wsgi:app`
- Environment variables: `APP_ENV=production`, `SECRET_KEY`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `FRONTEND_URL`

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/auth/login` | Log in with email and password |
| POST | `/api/auth/logout` | Log out |
| GET | `/api/auth/me` | Current doctor |
| GET | `/api/patients?doctor_id=` | List a doctor's patients |
| POST | `/api/patients/` | Create a patient (multipart, optional `dicom_file`s) |
| GET | `/api/patients/<id>` | Patient details and metrics |
| PUT | `/api/patients/<id>` | Update name / age |
| DELETE | `/api/patients/<id>` | Delete a patient |
| POST | `/api/patients/<id>/upload-dicom` | Upload a scan and run segmentation |
| POST | `/api/patients/<id>/re-segment` | Re-run segmentation on the stored scan |
| GET | `/api/patients/<id>/download/scan` | Download the scan (`.nii.gz`) |
| GET | `/api/patients/<id>/download/mask` | Download the mask (`.nii.gz`) |
| GET | `/api/patients/<id>/download/both` | Download both as a ZIP |

## Known limitations

- **Authorization:** the doctor id is still taken from the request; it will be replaced by
  Firebase ID token verification (`app/core/security.py`).
- **Confidence metric** is a placeholder; it will be computed from the model's softmax output.
- **File storage:** scans are stored as base64 in Firestore; Cloud Storage is the target.
- **Synchronous inference:** segmentation runs inside the request; a background job queue
  is planned for large scans.
- **Preprocessing** is a simplified version of nnU-Net's pipeline (no resampling to target
  spacing, no sliding window).
- This is a research prototype, not a validated medical device.
