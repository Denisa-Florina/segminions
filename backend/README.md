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

## Inference pipeline

`app/ml/inference.py` reproduces nnU-Net's 2D inference without depending on the
`nnunetv2` package (which pulls in many heavy dependencies):

1. **DICOM → NIfTI** (`dicom_converter.py`): stored values are converted to Hounsfield
   units (`RescaleSlope` / `RescaleIntercept`), axes follow the NIfTI convention
   (x = columns, y = rows, z = slices), and the slice spacing comes from the slice positions.
2. **Orientation:** nnU-Net reads images with SimpleITK (arrays indexed z, y, x), nibabel
   uses x, y, z, so each slice is transposed to (y, x) before the model and back after.
3. **Normalisation** with the dataset's CT intensity statistics from `plans.json`.
4. **Resampling** of each slice to the training spacing (0.4 mm).
5. **Sliding window** over 56×128 patches with 50% overlap and Gaussian weighting
   (`sliding_window.py`), optionally with test-time mirroring.
6. Logits are resampled back to the original slice size, converted to probabilities and
   thresholded at 0.5.

If the model cannot be loaded the app refuses to start, unless `ALLOW_SIMULATION=true`
(default in development), in which case results are explicitly marked `simulated`.
Inference errors are returned as errors, never replaced by a placeholder mask.

## Background segmentation

Segmentation can take minutes on a small CPU, so it does not run inside the request:

1. The request converts and validates the scan (bad files and scans that are too large
   are rejected immediately with `400`), stores it, sets the patient to `processing`
   and returns.
2. A background queue (`app/core/job_queue.py`) runs one segmentation at a time, to keep
   memory bounded; at most `MAX_PENDING_JOBS` scans wait (`503` beyond that).
3. The job sets `completed` (metrics + mask) or `failed` (with a message that never
   exposes internal errors). The frontend polls the patient until the status changes.

Status flow: `pending` (no scan) → `processing` → `completed` | `failed`.
A new upload or re-segment is refused with `409` while one is processing.

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/auth/login` | Log in with email and password, returns a JWT access token |
| POST | `/api/auth/logout` | Log out (the client discards its token) |
| GET | `/api/auth/me` | Current doctor |
| GET | `/api/patients` | List the authenticated doctor's patients |
| POST | `/api/patients/` | Create a patient (multipart, optional `dicom_file`s; segmentation starts in the background) |
| GET | `/api/patients/<id>` | Patient details and metrics |
| PUT | `/api/patients/<id>` | Update name / age |
| DELETE | `/api/patients/<id>` | Delete a patient |
| POST | `/api/patients/<id>/upload-dicom` | Upload a scan, start segmentation (`202`) |
| POST | `/api/patients/<id>/re-segment` | Re-run segmentation on the stored scan (`202`) |
| GET | `/api/patients/<id>/download/scan` | Download the scan (`.nii.gz`) |
| GET | `/api/patients/<id>/download/mask` | Download the mask (`.nii.gz`) |
| GET | `/api/patients/<id>/download/both` | Download both as a ZIP |

## Known limitations

- **Token revocation:** tokens are stateless, so logout cannot invalidate a token before it
  expires. A short TTL with refresh tokens, or a deny-list, would address this.
- **No rate limiting** on login yet (e.g. Flask-Limiter).
- **Confidence** is the mean softmax probability over the segmented voxels, so it is
  always ≥ 50% and says nothing about missed regions. Softmax probabilities are not
  calibrated; mirroring (`INFERENCE_MIRRORING`) or an ensemble of the 5 nnU-Net folds
  would give a better uncertainty estimate (only fold 0 is shipped).
- **Input domain:** the model was trained on ~2×2×5 cm crops at 0.4 mm. Whole CT scans
  are processed correctly but slowly (hundreds of patches per slice) and contain anatomy
  the model never saw; a localisation and cropping step is needed for full scans.
- **Inference cost:** each scan is limited to `MAX_INFERENCE_PATCHES` model passes
  (default 500, about 4 minutes on a 0.1 CPU instance); larger scans get a 400 error.
- **File storage:** scans are stored as base64 in Firestore (chunked above 512 KB);
  Cloud Storage is the target, and only `app/storage/file_storage.py` would change.
- **In-process job queue:** jobs live in the web process, so a restart loses queued and
  running jobs. They are detected (`processing` for longer than
  `JOB_STALE_AFTER_MINUTES`) and reported as failed, and the user can re-segment. A
  dedicated worker with a persistent queue (Cloud Tasks, RQ/Celery) would remove this.
- **Orientation:** DICOM direction cosines (`ImageOrientationPatient`) are not applied;
  slices are assumed axial and in the standard row/column order.
- This is a research prototype, not a validated medical device.
