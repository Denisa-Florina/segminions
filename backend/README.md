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
- Start command: `gunicorn wsgi:app --workers 1 --timeout 300` (one worker: the model is loaded once per worker and inference can take minutes on a small CPU)
- Environment variables: `APP_ENV=production`, `SECRET_KEY`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `FRONTEND_URL`

## Security

- **Authentication:** `POST /api/auth/login` returns a signed JWT (HS256, `SECRET_KEY`,
  expires after `ACCESS_TOKEN_TTL_MINUTES`, default 8 h). Every `/api/patients` request must
  send `Authorization: Bearer <token>`.
- **Authorization:** the doctor is identified only from the token. Each patient operation
  checks ownership; another doctor's patient is answered with `404`, so its existence is
  not revealed.
- **Passwords** are hashed with bcrypt. Legacy unsalted SHA-256 hashes are verified once
  and upgraded to bcrypt on the next successful login.
- Login returns the same error for an unknown email and a wrong password.

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/auth/login` | Log in with email and password, returns a JWT access token |
| POST | `/api/auth/logout` | Log out (the client discards its token) |
| GET | `/api/auth/me` | Current doctor |
| GET | `/api/patients` | List the authenticated doctor's patients |
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

- **Token revocation:** tokens are stateless, so logout cannot invalidate a token before it
  expires. A short TTL with refresh tokens, or a deny-list, would address this.
- **No rate limiting** on login yet (e.g. Flask-Limiter).
- **Confidence** is the mean softmax probability over the segmented voxels. Softmax
  probabilities are not calibrated; test-time augmentation (mirroring) or an ensemble of
  the 5 nnU-Net folds would give a better uncertainty estimate.
- **Input domain:** the model was trained on ~2×2×5 cm crops at 0.4 mm. Whole CT slices
  are resized to the 56×128 patch, which shrinks the target structure; a localisation and
  cropping step before segmentation is needed for full scans.
- **File storage:** scans are stored as base64 in Firestore; Cloud Storage is the target.
- **Synchronous inference:** segmentation runs inside the request; a background job queue
  is planned for large scans.
- **Preprocessing** is a simplified version of nnU-Net's pipeline (no resampling to target
  spacing, no sliding window).
- This is a research prototype, not a validated medical device.
