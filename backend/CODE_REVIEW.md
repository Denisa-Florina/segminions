# Backend Code Review

A senior-level review of the whole backend (`app/`, ~1,750 lines), covering correctness,
architecture, OOP/SOLID, clean code, persistence, concurrency, security, the ML pipeline,
API design and tooling.

**Severity**

| | Meaning |
|---|---|
| 🟠 | Important: design or robustness problem worth fixing soon |
| 🟡 | Improvement: makes the code cleaner, safer or easier to change |
| ⚪ | Nit: small, optional |

---

## Contents

1. [Summary](#1-summary)
2. [Architecture](#2-architecture)
3. [OOP and SOLID](#3-oop-and-solid)
4. [Clean code](#4-clean-code)
5. [Persistence and storage](#5-persistence-and-storage)
6. [Background jobs and concurrency](#6-background-jobs-and-concurrency)
7. [Security](#7-security)
8. [ML pipeline](#8-ml-pipeline)
9. [API design](#9-api-design)
10. [Testing and tooling](#10-testing-and-tooling)
11. [Operations](#11-operations)
12. [What is already good](#12-what-is-already-good)
13. [Suggested order of work](#13-suggested-order-of-work)

---

## 1. Summary

The backend has a sound shape: a layered architecture (`api → services → repositories /
storage / ml`), an application factory, typed exceptions mapped to HTTP codes, Pydantic
validation, JWT authentication with per-doctor authorization, and ~50 focused tests run by CI
on every push.

The main remaining weaknesses:

- **Dicts instead of domain objects**: patients, metrics and statuses travel as plain
  `dict`s and strings, so the rules about them are spread over several files.
- **Hidden coupling between layers**: services read Flask's `current_app`, the API
  imports storage constants, and two classes write to the same Firestore document.
- **Global singletons** wired at import time, which forces tests to monkeypatch private
  attributes.

| # | Finding | Severity |
|---|---|---|
| 2.1 | Services depend on Flask (`current_app`) | 🟠 |
| 2.2 | Global singletons and module-level wiring | 🟠 |
| 2.3 | Two classes own the same Firestore document | 🟠 |
| 2.4 | API layer imports storage constants | 🟡 |
| 3.1 | Primitive obsession: dicts and strings instead of domain types | 🟠 |
| 3.2 | `PatientService` has too many responsibilities | 🟡 |
| 3.3 | Services depend on concrete classes, not abstractions | 🟡 |
| 3.4 | Simulation handled with `if` branches instead of polymorphism | 🟡 |
| 4.x | Duplication, naming | 🟡 / ⚪ |
| 5.1 | File writes are not atomic | 🟡 |
| 5.2 | Downloads load whole files (and their base64 copy) into memory | 🟡 |
| 6.1 | Jobs are not recovered after a restart | 🟡 |
| 6.2 | One sync worker: a long upload blocks every other request | 🟡 |
| 7.x | Tokens after password change, no rate limit | 🟡 |
| 8.x | DICOM series validation, extension filter, hard-coded architecture, checkpoint integrity | 🟠 / 🟡 |
| 10.x | No type checker, tests patch private attributes | 🟡 |

---

## 2. Architecture

### 2.1 🟠 Services depend on Flask

**Where:** [app/services/patient_service.py:172](app/services/patient_service.py#L172),
[app/services/patient_service.py:221](app/services/patient_service.py#L221)

`PatientService` reads `current_app.config[...]`. That ties the business layer to Flask
and to a request context:

- the service cannot be used from a CLI script, a worker process or a test without a
  Flask app;
- `run_segmentation` runs in a background thread, where `current_app` does **not** exist.
  It works today only because that method happens not to read the config. If someone adds
  a `current_app` call to the job later, it fails with `RuntimeError: Working outside of
  application context`, and only in production.

**Fix:** pass the settings the service needs into its constructor:

```python
@dataclass(frozen=True)
class PatientSettings:
    max_dicom_files: int
    job_stale_after: timedelta

class PatientService:
    def __init__(self, patients, files, segmenter, jobs, settings: PatientSettings): ...
```

### 2.2 🟠 Global singletons and module-level wiring

**Where:** [app/extensions.py:11-13](app/extensions.py#L11-L13),
[app/services/patient_service.py:230-232](app/services/patient_service.py#L230-L232),
[app/services/auth_service.py:48](app/services/auth_service.py#L48)

The database client, model and queue are module globals changed with `global`. The
services are created at import time (`patient_service = PatientService(...)`), and the
API modules import those instances directly. The consequences:

- the dependency graph is invisible: you cannot see from the code what `patients.py`
  really depends on;
- two app instances (for example two test configurations) share the same state;
- tests have to monkeypatch **private** attributes (`patient_service._segmenter_provider`,
  `_job_queue_provider`). Those tests break when internals are renamed (see 10.2).

**Fix:** build the object graph once, inside `create_app`, and attach it to the app.
This is the *composition root* pattern:

```python
# app/container.py
@dataclass
class Container:
    auth: AuthService
    patients: PatientService

def build_container(config, db, segmenter, jobs) -> Container: ...

# create_app
app.extensions["container"] = build_container(...)

# in a route
def services() -> Container:
    return current_app.extensions["container"]
```

Tests can then build a `Container` with fakes passed in through constructors, with no
monkeypatching at all.

### 2.3 🟠 Two classes own the same Firestore document

**Where:** [app/storage/file_storage.py:40-41](app/storage/file_storage.py#L40-L41),
[app/repositories/patient_repository.py:10](app/repositories/patient_repository.py#L10)

`FirestoreFileStorage` writes `scan_data`, `*_filename`, `*_is_chunked`, `updated_at`,
etc. **into the patient document**. `PatientRepository` has to know those field names in
order to strip them (`_FILE_FIELDS`). Each class depends on the other's internal layout,
so the encapsulation is broken. It is also why the storage cannot really be replaced "by
changing one module", as its docstring claims.

**Fix:** give files their own collection (`files/{patient_id}_{kind}` with chunks
underneath). The patient document then holds no file data at all, and a later move to
Cloud Storage really does touch only `storage/`.

### 2.4 🟡 The API layer imports storage constants

**Where:** [app/api/patients.py:15](app/api/patients.py#L15)

`from app.storage.file_storage import MASK, SCAN` makes the HTTP layer depend on the
storage layer's key names (`"scan_data"`), skipping the service layer.

**Fix:** a domain enum, `class FileKind(StrEnum): SCAN = "scan"; MASK = "mask"`, or
service methods `get_scan(...)` and `get_mask(...)`.

---

## 3. OOP and SOLID

### 3.1 🟠 Primitive obsession: dicts and strings instead of domain types

Patients, metrics and statuses are passed around as `dict` and `str`:

- the status strings are defined in [patient_service.py:31](app/services/patient_service.py#L31),
  repeated as a `Literal` in [schemas/patient.py:68](app/schemas/patient.py#L68), and
  again in the frontend;
- the dict keys (`"metrics"`, `"status"`, `"processing_started_at"`, `"doctor_id"`)
  are typed by hand in many places, and a typo fails silently (`patient.get("staus")`
  returns `None`);
- the rules that belong to a patient, such as "is it owned by this doctor?", "can a job
  start?" and "is the job stale?", live in the service as functions that receive a dict.

**Fix:** a small domain model.

```python
class PatientStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Patient:
    id: str
    doctor_id: str
    name: str
    age: int
    status: PatientStatus
    metrics: SegmentationMetrics | None
    processing_started_at: datetime | None
    segmentation_error: str | None

    def is_owned_by(self, doctor_id: str) -> bool: ...
    def start_processing(self, now: datetime) -> None:      # raises if already processing
        ...
    def is_stale(self, now: datetime, after: timedelta) -> bool: ...
```

The repository converts Firestore documents to `Patient` objects and back, the service
works with `Patient`, and the API serialises it. The state machine
(`pending → processing → completed/failed`) is then in one place and can be unit-tested
without Flask or Firestore. The same applies to metrics:
[calculate_metrics](app/ml/metrics.py#L8) should return a frozen dataclass, not a dict.

### 3.2 🟡 `PatientService` has too many responsibilities (SRP)

**Where:** [app/services/patient_service.py](app/services/patient_service.py), 232 lines

It handles patient CRUD, ownership checks, DICOM preparation, job submission, the job
itself, stale-job detection and ZIP export. These change for different reasons.

**Fix:** split along those reasons:

- `PatientService`: CRUD and ownership;
- `SegmentationService`: `start(patient)`, `run(job)`, `expire_stale()`;
- `ResultExporter`: building the ZIP.

### 3.3 🟡 Services depend on concrete classes (DIP)

**Where:** [app/services/patient_service.py:51-61](app/services/patient_service.py#L51-L61)

The constructor is typed with `PatientRepository` and `FirestoreFileStorage` (concrete
classes), while `segmenter_provider` and `job_queue_provider` have no type at all. The
service is written against Firestore, not against what it actually needs.

**Fix:** define the interfaces the service consumes as `Protocol`s, in the service (or
domain) layer:

```python
class PatientStore(Protocol):
    def get(self, patient_id: str) -> Patient | None: ...
    def save(self, patient: Patient) -> None: ...

class FileStore(Protocol):
    def save(self, patient_id: str, kind: FileKind, data: bytes, filename: str) -> None: ...
    def load(self, patient_id: str, kind: FileKind) -> StoredFile | None: ...

class SegmentationModel(Protocol):
    def check_scan(self, scan: bytes) -> None: ...
    def segment(self, scan: bytes) -> SegmentationResult: ...
```

Firestore, Cloud Storage and in-memory fakes all implement these. Tests then pass fakes
in through the constructor, and the type checker verifies that they match.

### 3.4 🟡 Simulation is handled with `if` branches (OCP / polymorphism)

**Where:** [app/ml/inference.py:75](app/ml/inference.py#L75),
[app/ml/inference.py:81](app/ml/inference.py#L81)

`Segmenter` checks `if self._model is None` in several methods, and the
`allow_simulation` decision is made inside its constructor. One class with a null model
inside is acting as two different implementations.

**Fix:** two classes behind the same protocol (`NnUnetSegmenter`, `SimulatedSegmenter`),
with the choice made once at startup in the composition root. Neither class then needs
to know the other exists, and adding a third, for example an ONNX implementation, needs
no changes to existing code.

### 3.5 ⚪ Side effect in a constructor

[app/ml/inference.py:54](app/ml/inference.py#L54) calls `torch.set_num_threads()`, which
changes the setting for the **whole process**. Do it at startup in `create_app`, where
process-wide configuration belongs.

---

## 4. Clean code

### 4.1 🟡 Repeated "mark failed" code (DRY)

`_mark_failed` exists, but `{"status": FAILED, "segmentation_error": ...}` is still
written by hand in `run_segmentation`
([:172](app/services/patient_service.py#L172), [:186](app/services/patient_service.py#L186))
and in `_expire_if_stale` ([:278](app/services/patient_service.py#L278)). Better:
`patient.fail(message)` on the domain object (see 3.1).

### 4.2 🟡 Ambiguous names

| Name | Problem | Suggestion |
|---|---|---|
| `date` | Set at creation **and overwritten on every segmentation** ([:192](app/services/patient_service.py#L192)), so it is neither "created" nor "scan date" | `scan_date` (from DICOM `StudyDate`) and `segmented_at` |
| `filename` | A generated name (`<first file>_16slices.nii.gz`), not the uploaded file | `scan_filename` |
| `file_size` | The size of the converted NIfTI, not the upload | `scan_size_bytes` |

### 4.3 ⚪ Smaller items

- [schemas/patient.py:22](app/schemas/patient.py#L22): `validate_input` reports only the
  first validation error. Return them all (for example as `details`), so that a form can
  highlight every invalid field.
- [inference.py:37](app/ml/inference.py#L37): `_ScanPlan.image: object` should be
  `nib.Nifti1Image`.
- [auth_service.py:14](app/services/auth_service.py#L14): `_DUMMY_HASH` runs bcrypt
  (~0.25 s) at import time, slowing every startup and test run. Compute it lazily
  (`functools.cache`).
- Mark value objects as `@dataclass(frozen=True)` (`NiftiScan`, `StoredFile`), so that
  nothing modifies them by accident.

---

## 5. Persistence and storage

### 5.1 🟡 File writes are not atomic

**Where:** [app/storage/file_storage.py:55-75](app/storage/file_storage.py#L55-L75)

`save()` deletes the old chunks, writes the new ones, then updates the metadata, as
separate operations. A download running at the same moment (or a crash in between) can
see half-written chunks, or chunks that don't match the metadata, and return a corrupt
file. The deletes are also one round trip per chunk
([:125-127](app/storage/file_storage.py#L125-L127)).

**Fix:** write the new chunks under a new version (`.../v{n}/chunk_i`), switch the
metadata to that version in one update, then delete the old version. Use
`db.batch()` / `bulk_writer()` for the many small writes and deletes.

### 5.2 🟡 Downloads hold whole files in memory

**Where:** [file_storage.py:77-94](app/storage/file_storage.py#L77-L94),
[api/patients.py:104](app/api/patients.py#L104)

A download keeps the base64 string, the decoded bytes and a `BytesIO` copy in memory at
the same time, next to a ~300 MB model on a 512 MB instance. A few concurrent downloads
of large scans can run out of memory. The proper solution is object storage with
**signed URLs**: the browser downloads straight from Cloud Storage, and the API never
handles the file contents.

### 5.3 🟡 Other data issues

- **No pagination** on `GET /patients`: it returns every patient on each poll. Add
  `limit` and a cursor (`start_after`), plus an explicit order (`created_at desc`).
- **Email uniqueness is not enforced**: two doctor documents with the same email make
  `limit(1)` return either of them at random. Use the normalised email as the document
  id, or check uniqueness inside a transaction when creating an account.
- **Repeated reads**: `build_results_zip` reads the patient document 5 times (one `get`,
  then `get_file` twice, each of which does a `get` plus a `load`). Load the patient
  once and pass it along.

---

## 6. Background jobs and concurrency

### 6.1 🟡 Jobs are not recovered after a restart

**Where:** [app/core/job_queue.py](app/core/job_queue.py)

Every deploy on Render restarts the process. Queued and running jobs are lost, and users
wait `JOB_STALE_AFTER_MINUTES` (20 minutes) before seeing "failed". The scan is already
stored, so the job could simply be **restarted** instead:

- at startup, find patients with `status == "processing"` and queue them again (with a new job id);
- on `SIGTERM`, stop accepting new jobs, so that a running job is not cut off without
  being recorded.

Marking stale jobs failed during `GET` requests also means reads write to the database
(a command-query separation violation). Recovery at startup makes most of that code
unnecessary.

### 6.2 🟡 One sync worker serialises all requests

**Where:** [render.yaml](render.yaml) (`gunicorn wsgi:app --workers 1`)

The default sync worker handles **one request at a time**. While one doctor uploads and
converts a large DICOM series, every other request waits: other doctors' polling, logins,
and Render's health check (Render may restart a service that fails its health check).

**Fix:** `--worker-class gthread --threads 4`. This keeps a single process, so the model
is loaded once, but lets requests run in parallel. It also makes the
check-then-set race in `_ensure_not_processing` possible, so do it together with a
Firestore transaction for "claim the patient for processing":

```python
@firestore.transactional
def claim(transaction, ref, job_id):
    snapshot = ref.get(transaction=transaction)
    if snapshot.get("status") == "processing":
        raise ConflictError("Segmentation is already in progress")
    transaction.update(ref, {"status": "processing", "job_id": job_id, ...})
```

### 6.3 ⚪ The queue's capacity is global

`MAX_PENDING_JOBS = 3` is shared by all doctors, so one doctor can fill the queue for
everyone. A per-doctor limit is fairer.

---

## 7. Security

### 7.1 🟡 Tokens stay valid after a password change or account removal

**Where:** [app/core/security.py:65-72](app/core/security.py#L65-L72)

The JWT is checked only for its signature and expiry. After a password change (for
example after a compromise), old tokens keep working for up to 8 hours. A deleted doctor
can still call the patient endpoints, and `/me` then returns `404` where `401` would be
right ([auth_service.py:41-45](app/services/auth_service.py#L41-L45)).

**Fix:** store `password_changed_at` (or a `token_version`) on the doctor and reject
tokens issued before it. Short-lived access tokens with refresh tokens are the standard
way to keep this check cheap.

### 7.2 🟡 Other items

- **No rate limiting on login.** bcrypt slows brute-forcing down but does not stop it.
  Add Flask-Limiter (for example 5 attempts per minute per IP and per email).
- **The checkpoint is loaded with `weights_only=False`**
  ([model_loader.py:101](app/ml/model_loader.py#L101)). That runs arbitrary pickle code,
  so anyone who can replace the file gets code execution. Record the file's SHA-256 and
  check it before loading, or convert the weights once to `safetensors`.
- **No audit log** of who viewed or downloaded which patient's data. For medical data
  this is usually a requirement (GDPR, hospital policy).
- **The uploaded file name** ends up in `filename` and in the ZIP entry names. DICOM
  exports are often named after the patient. Use a generated name such as
  `scan_<patient_id>.nii.gz`.

---

## 8. ML pipeline

### 8.1 🟠 DICOM series are not validated

**Where:** [app/ml/dicom_converter.py:54-89](app/ml/dicom_converter.py#L54-L89)

Every uploaded `.dcm` file is stacked into a single volume. There are no checks that:

- all files belong to **one series** (`SeriesInstanceUID`). Uploading two series of the
  same size produces an interleaved, meaningless volume, and nothing reports an error;
- all slices have the same `Rows` / `Columns` / `PixelSpacing`. Different sizes currently
  fail in `np.stack` with the generic message "conversion failed";
- the modality is CT (`Modality == "CT"`), since the HU normalisation assumes CT;
- no slice position appears twice.

**Fix:** group the files by `SeriesInstanceUID`. Reject an upload that contains more than
one series, or mixed geometry, with a specific message.

### 8.2 🟡 Files are filtered by extension

[dicom_converter.py:58](app/ml/dicom_converter.py#L58) skips files that don't end in
`.dcm`. Many PACS and CD exports have **no extension** (`IM000001`). Detect DICOM by
content instead: the `DICM` marker at byte 128, or simply try `pydicom.dcmread`.

### 8.3 🟡 The network architecture is hard-coded

[model_loader.py:72-93](app/ml/model_loader.py#L72-L93) hard-codes `PlainConvUNet`,
`Conv2d`, `InstanceNorm2d` and `LeakyReLU`. But `plans.json` names the network class and
its operations (`architecture.network_class_name`, `_kw_requires_import`). If the model
is retrained with another nnU-Net configuration (for example ResEnc), loading fails,
which is the better case. In the worse case, a model is built that does not match its
weights. Read the class and its operations from the plans (nnU-Net's own
`get_network_from_plans` does exactly this), or at least check that the plans contain
what the code assumes.

### 8.4 🟡 Inference is not reproducible or traceable

A result does not record **which** model produced it. Store a `model_version` (for
example the checkpoint's SHA-256 and the nnU-Net fold) together with the metrics. When
the model is retrained, you can then tell which results came from which version. That is
essential for any medical or research use.

### 8.5 ⚪ Smaller items

- DICOM direction cosines (`ImageOrientationPatient`) are ignored and all slices are
  assumed axial. This is already documented as a limitation. Reject non-axial series
  explicitly rather than processing them wrongly.
- `simulate_segmentation` returns a `(1, 1, 1)` mask when anything fails
  ([simulation.py:36-38](app/ml/simulation.py#L36-L38)). It is development-only code, but
  it could just raise.

---

## 9. API design

### 9.1 🟡 Response shapes are inconsistent

| Endpoint | Returns |
|---|---|
| `POST /patients/` | `{"patient": Summary}` |
| `POST /patients/<id>/upload-dicom` | `{"result": {"status"}}` |
| `POST /patients/<id>/re-segment` | `{"patient": Detail}` |

A client has to know each shape separately. Return the same patient representation
(`PatientDetail`) from every endpoint that changes a patient.

### 9.2 ⚪ Resource-oriented URLs

`/upload-dicom` and `/re-segment` are verbs. A more RESTful layout:

| Current | Suggested |
|---|---|
| `POST /patients/<id>/upload-dicom` | `PUT /patients/<id>/scan` |
| `POST /patients/<id>/re-segment` | `POST /patients/<id>/segmentations` |
| `GET /patients/<id>/download/scan` | `GET /patients/<id>/scan` |
| `GET /patients/<id>/download/mask` | `GET /patients/<id>/mask` |

Other suggestions:
- version the API (`/api/v1/...`) before external clients depend on it;
- generate the OpenAPI documentation from the Pydantic schemas (for example with
  `flask-smorest` or `spectree`), or migrate to FastAPI, which generates it out of the
  box.

### 9.3 ⚪ The health check says nothing about readiness

[health.py](app/api/health.py) always returns `healthy`. Report what actually matters:
whether the model is loaded, the queue length, and whether Firestore
is reachable. Use two endpoints: `/health/live` (the process is up) and `/health/ready`
(the app can serve requests).

---

## 10. Testing and tooling

### 10.1 🟡 No type checker

The code has type hints, but nothing checks them. Add `mypy` (or `pyright`) in strict
mode for `app/`. It would have flagged the untyped providers (3.3), and together with
domain types (3.1) it catches the typos that dict keys allow.

### 10.2 🟡 Tests patch private attributes

[tests/conftest.py](tests/conftest.py) monkeypatches `patient_service._segmenter_provider`,
`auth_service.doctors.get_by_email`, and so on. These tests depend on implementation
details: renaming a private attribute breaks them although the behaviour is unchanged.
With constructor injection (2.2 / 3.3) the tests build the service with fakes instead.

### 10.3 🟡 Missing kinds of tests

- **Firestore emulator tests** for the repositories and storage. The current
  `FakeFirestore` only imitates the API, so it cannot catch real Firestore behaviour
  (for example subcollections surviving their parent).
- **A regression test for the model**: one small real CT crop with its ground-truth
  label, asserting a minimum Dice. It catches preprocessing regressions such as the
  orientation, HU and resampling bugs fixed earlier.
- A coverage report (`pytest --cov`), so that untested code is visible.

### 10.4 ⚪ Inconsistent Python versions

Render uses 3.11, local tests ran on 3.10, and `pyproject.toml` targets `py310`. Pin one
version everywhere (`.python-version`, `render.yaml`, the CI workflow, ruff's
`target-version`).

---

## 11. Operations

- 🟡 **The 60 MB model checkpoint is committed to git.** Every clone downloads it, and
  every new version stays in the history forever. Use Git LFS, or download it at build
  time from a release or bucket, with a checksum check.
- 🟡 **Configuration is read at import time** ([config.py:14-55](app/config.py#L14-L55)).
  The class attributes are evaluated once, when the module is imported. A wrong value
  (`MAX_PENDING_JOBS=abc`) crashes the import with a bare `ValueError` that doesn't name
  the variable. `pydantic-settings` (`BaseSettings`) validates and documents every
  setting in one typed class and gives clear errors.
- 🟡 **Logs** are plain text with no request id. Structured (JSON) logs with a
  per-request correlation id, also passed into the background job, make it possible to
  follow one upload from the request to the end of its job.
- ⚪ **No `Dockerfile`.** The deployment depends on how Render sets things up. A
  container makes local runs, CI and production identical.
- ⚪ `get_config` still falls back to `FLASK_ENV`, which Flask has deprecated. Use only
  `APP_ENV`.

---

## 12. What is already good

These are worth pointing out in an interview.

- **A clear layered architecture**, with the ML package independent of Flask and
  Firebase.
- **An application factory** with configuration per environment, and a production
  start that refuses to run without `SECRET_KEY` or a model.
- **Typed application exceptions** mapped to HTTP status codes in one place. Unexpected
  errors are logged and never leaked to clients.
- **Authentication and authorization**: JWT, bcrypt password hashes, the same error for an unknown email and a wrong password (and the same
  response time), and ownership checks that answer `404` for another doctor's patients.
- **Input validation with Pydantic** at the API boundary.
- **A faithful re-implementation of nnU-Net's 2D inference** (HU conversion,
  orientation, resampling, Gaussian sliding window, mirroring), tested against stub
  networks, including a test that fails when the orientation is wrong.
- **Background processing** with a bounded queue, an explicit status machine, and
  failures recorded instead of silently replaced by fake results.
- **Background jobs that cannot corrupt data**: each job has an id, only the patient's
  current job writes a result, and a patient cannot be deleted while it is processing.
- **Responses built from whitelisted schemas**, so no internal field reaches a client.
- **~50 focused tests** that run in seconds without credentials, a GPU or a network connection,
  and a CI workflow that runs them, with `ruff` and the frontend build, on every push.

---

## 13. Suggested order of work

| Priority | Item | Effort |
|---|---|---|
| 1 | 2.1, 2.2, 3.3 Settings in constructors, composition root, protocols | half a day |
| 2 | 3.1 `Patient` domain model and `PatientStatus` enum | half a day |
| 3 | 2.3 and 5.x Files in their own collection, then Cloud Storage with signed URLs | 1 day |
| 4 | 6.1 and 6.2 Job recovery at startup, threaded workers with a transactional claim | 1 day |
| 5 | 8.1–8.4 DICOM series validation, architecture from plans, model versioning | 1 day |

Items 1–2 are the refactoring that makes the code base clearly "senior". Items 3–5 are
what a production deployment would need.
