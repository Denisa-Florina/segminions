# Backend Code Review

A senior-level review of the whole backend (`app/`, ~1,750 lines), covering correctness,
architecture, OOP/SOLID, clean code, persistence, concurrency, security, the ML pipeline,
API design and tooling.

Findings marked **verified** were reproduced by running code. The others come from
reading the code, and the reasoning is given.

**Severity**

| | Meaning |
|---|---|
| 🔴 | Bug: wrong behaviour users can hit |
| 🟠 | Important: design or robustness problem worth fixing soon |
| 🟡 | Improvement: makes the code cleaner, safer or easier to change |
| ⚪ | Nit: small, optional |

---

## Contents

1. [Summary](#1-summary)
2. [Bugs](#2-bugs)
3. [Architecture](#3-architecture)
4. [OOP and SOLID](#4-oop-and-solid)
5. [Clean code](#5-clean-code)
6. [Persistence and storage](#6-persistence-and-storage)
7. [Background jobs and concurrency](#7-background-jobs-and-concurrency)
8. [Security](#8-security)
9. [ML pipeline](#9-ml-pipeline)
10. [API design](#10-api-design)
11. [Testing and tooling](#11-testing-and-tooling)
12. [Operations](#12-operations)
13. [What is already good](#13-what-is-already-good)
14. [Suggested order of work](#14-suggested-order-of-work)

---

## 1. Summary

The backend has a sound shape: a layered architecture (`api → services → repositories /
storage / ml`), an application factory, typed exceptions mapped to HTTP codes, Pydantic
validation, JWT authentication with per-doctor authorization, and ~95 tests.

The main remaining weaknesses:

- **One serious bug**: files named `.nii.gz` are not gzip-compressed, so downloaded
  results cannot be opened by standard tools (verified).
- **Dicts instead of domain objects**: patients, metrics and statuses travel as plain
  `dict`s and strings, so the rules about them are spread over several files.
- **Hidden coupling between layers**: services read Flask's `current_app`, the API
  imports storage constants, and two classes write to the same Firestore document.
- **Global singletons** wired at import time, which forces tests to monkeypatch private
  attributes.
- **Background jobs are not idempotent**: a late job can overwrite the result of a newer
  one, and a job can orphan data if the patient is deleted while it runs.

| # | Finding | Severity |
|---|---|---|
| 2.1 | `.nii.gz` files are not gzip-compressed (unreadable downloads, 800× larger) | ✅ fixed |
| 2.2 | Deleting a patient during segmentation orphans the mask chunks | ✅ fixed |
| 2.3 | A stale job can overwrite the result of a newer scan | ✅ fixed |
| 2.4 | Email login is case-sensitive | ✅ fixed |
| 2.5 | Internal error messages can reach users through `segmentation_error` | ✅ fixed |
| 3.1 | Services depend on Flask (`current_app`) | 🟠 |
| 3.2 | Global singletons and module-level wiring | 🟠 |
| 3.3 | Two classes own the same Firestore document | 🟠 |
| 3.4 | Persistence concerns (legacy fields) live in API schemas | 🟡 |
| 3.5 | API layer imports storage constants | 🟡 |
| 4.1 | Primitive obsession: dicts and strings instead of domain types | 🟠 |
| 4.2 | `PatientService` has too many responsibilities | 🟡 |
| 4.3 | Services depend on concrete classes, not abstractions | 🟡 |
| 4.4 | Simulation handled with `if` branches instead of polymorphism | 🟡 |
| 5.x | Duplication, naming, two sources of truth for status | 🟡 / ⚪ |
| 6.1 | Listing patients downloads their base64 files | 🟠 |
| 6.2 | Naive local datetimes stored as if they were UTC | 🟠 |
| 6.3 | File writes are not atomic | 🟡 |
| 6.4 | Downloads load whole files (and their base64 copy) into memory | 🟡 |
| 7.1 | Jobs are not recovered after a restart | 🟡 |
| 7.2 | One sync worker: a long upload blocks every other request | 🟡 |
| 8.x | Response blacklisting, tokens after password change, no rate limit | 🟠 / 🟡 |
| 9.x | DICOM series validation, extension filter, hard-coded architecture, checkpoint integrity | 🟠 / 🟡 |
| 11.x | No CI, no type checker, tests patch private attributes | 🟡 |

---

## 2. Bugs

> **Status:** all five items in this section are fixed, with regression tests in
> [tests/test_review_fixes.py](tests/test_review_fixes.py). The notes below describe
> the original problems.
>
> - 2.1: `write_nifti` gzip-compresses; `read_nifti` reads both formats; downloads and
>   the ZIP export compress files stored by earlier versions on the fly.
> - 2.2: deleting a patient while it is processing returns `409`; a job whose patient
>   disappears writes nothing, or deletes what it had already written.
> - 2.3: each job has an id stored on the patient; a job only writes its result while it
>   is still the patient's current job.
> - 2.4: emails are normalised (`strip().lower()`); accounts stored with capitals are
>   found as typed and normalised on their first login.
> - 2.5: only application messages are stored in `segmentation_error`.

### 2.1 🔴 `.nii.gz` files are not gzip-compressed — *verified*

**Where:** [app/ml/nifti_io.py:15-20](app/ml/nifti_io.py#L15-L20),
[app/ml/dicom_converter.py:49](app/ml/dicom_converter.py#L49),
[app/api/patients.py:104-107](app/api/patients.py#L104-L107)

`write_nifti` writes the image into a plain `BytesIO`, which produces **uncompressed**
NIfTI. The file is still named `*.nii.gz` and served as `application/gzip`.

Reproduced with a 211×148×16 mask:

```
first bytes: 5c01        (a gzip file starts with 1f8b)
stored size: 976 KB, gzipped it would be 1.2 KB
nibabel.load("mask.nii.gz") -> ImageFileError
```

**Impact:**
- Doctors cannot open the downloaded scan or mask in nibabel. Viewers such as
  3D Slicer and ITK-SNAP pick the decompression from the extension, so they would
  most likely fail too.
- Masks are mostly zeros and compress about 800×. Without compression they take up
  far more Firestore storage, chunk documents, memory and transfer time than needed.

**Fix:** compress when writing, and accept both formats when reading, so that files
already stored keep working:

```python
import gzip

def write_nifti(data, affine) -> BytesIO:
    raw = nib.Nifti1Image(data, affine).to_bytes()
    return BytesIO(gzip.compress(raw, compresslevel=6))

def read_nifti(stream: BytesIO) -> nib.Nifti1Image:
    data = stream.getvalue()
    if data[:2] == b"\x1f\x8b":          # gzip magic number
        data = gzip.decompress(data)
    return nib.Nifti1Image.from_bytes(data)
```

Add a test that writes a file to disk and opens it with `nibabel.load`. That is what a
user does with a download, and it is what the current tests never check.

### 2.2 🔴 Deleting a patient during segmentation orphans the mask

**Where:** [app/services/patient_service.py:150-160](app/services/patient_service.py#L150-L160),
[app/storage/file_storage.py:55-75](app/storage/file_storage.py#L55-L75)

`delete()` does not check whether a job is running. If the patient is deleted while
segmentation runs, `run_segmentation` then calls `files.save()`, which:

1. writes the chunk documents to `patients/<id>/mask_data_chunks/…`. Firestore allows
   subcollection documents under a parent that does not exist;
2. calls `update()` on the deleted parent, which raises `NotFound`.

The exception is caught and logged, but the chunks from step 1 stay in Firestore forever.
That is exactly the orphaned-medical-data problem that `delete_all` was written to
prevent. (Masks of normal scans exceed 512 KB uncompressed, so they are chunked. See 2.1.)

**Fix (any one of these):**
- refuse to delete while `status == "processing"` (`409`), or
- in `save()`, update the parent document **first** (it fails fast if the patient is
  gone) and write the chunks afterwards, or
- at the end of the job, re-check that the patient exists and call `delete_all` if not.

### 2.3 🔴 A stale job can overwrite the result of a newer scan

**Where:** [app/services/patient_service.py:162-165](app/services/patient_service.py#L162-L165),
[app/services/patient_service.py:215-227](app/services/patient_service.py#L215-L227)

The job writes its result without checking that it is still the current job. One possible
sequence:

1. Job A (scan A) runs slowly. After `JOB_STALE_AFTER_MINUTES` the patient is marked
   `failed`.
2. The doctor uploads scan B. Job B is queued behind A, because the queue runs one job
   at a time.
3. Job A finishes and writes mask A, `status = completed` and A's metrics.
4. Until job B finishes, the patient shows **completed with the mask of a different scan**.

**Fix:** give each job an id and write it on the patient when the job is queued. When the
job finishes, it only writes its result if the patient still has the same id (optimistic
concurrency). Ideally this check runs in a Firestore transaction:

```python
job_id = uuid4().hex
self.patients.update(patient_id, {**_processing_fields(), "job_id": job_id})
...
# in the job, before writing results:
if self.patients.get(patient_id).get("job_id") != job_id:
    logger.info("Discarding result of superseded job %s", job_id)
    return
```

### 2.4 🔴 Email login is case-sensitive

**Where:** [app/services/auth_service.py:26](app/services/auth_service.py#L26),
[app/repositories/doctor_repository.py:12-16](app/repositories/doctor_repository.py#L12-L16)

`where("email", "==", email)` is an exact match. A doctor registered as
`Ana.Pop@spital.ro` who types `ana.pop@spital.ro` gets "Invalid email or password".
Mobile keyboards often capitalise the first letter, so this happens a lot.

**Fix:** normalise with `email.strip().lower()` when an account is created and when the
user logs in. Run a one-off migration that lowercases the existing addresses.

### 2.5 🟠 Internal error messages can reach users

**Where:** [app/services/patient_service.py:203-207](app/services/patient_service.py#L203-L207)

```python
except Exception as error:
    ... "segmentation_error": getattr(error, "message", str(error))
```

For an `AppError` this is a safe message. For any other exception, for example a
`RuntimeError("Job queue is not initialised…")` or a Firestore error, `str(error)` is
stored and shown in the UI. The global handler takes care never to leak such details.

**Fix:** catch `AppError` explicitly. For anything else, store a generic message and log
the details.

---

## 3. Architecture

### 3.1 🟠 Services depend on Flask

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

### 3.2 🟠 Global singletons and module-level wiring

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
  `_job_queue_provider`). Those tests break when internals are renamed (see 11.3).

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

### 3.3 🟠 Two classes own the same Firestore document

**Where:** [app/storage/file_storage.py:40-41](app/storage/file_storage.py#L40-L41),
[app/repositories/patient_repository.py:10](app/repositories/patient_repository.py#L10)

`FirestoreFileStorage` writes `scan_data`, `*_filename`, `*_is_chunked`, `updated_at`,
etc. **into the patient document**. `PatientRepository` has to know those field names in
order to strip them (`_FILE_FIELDS`). Each class depends on the other's internal layout,
so the encapsulation is broken. It is also why the storage cannot really be replaced "by
changing one module", as its docstring claims.

**Fix:** give files their own collection (`files/{patient_id}_{kind}` with chunks
underneath). The patient document then holds no file data at all. That also fixes 6.1,
and a later move to Cloud Storage really does touch only `storage/`.

### 3.4 🟡 Persistence concerns live in the API schemas

**Where:** [app/schemas/patient.py:73-85](app/schemas/patient.py#L73-L85)

`PatientSummary.from_db` contains legacy fallbacks (`dicom_file` vs `filename`, and a
status derived from `segmented`). Mapping database rows to objects belongs to the
persistence layer. Legacy fallbacks should not live in code forever either.

**Fix:** move the mapping into the repository, which returns a `Patient` domain object
(see 4.1). Write a one-off migration script that backfills `status` and renames the old
fields, then delete the fallbacks.

### 3.5 🟡 The API layer imports storage constants

**Where:** [app/api/patients.py:15](app/api/patients.py#L15)

`from app.storage.file_storage import MASK, SCAN` makes the HTTP layer depend on the
storage layer's key names (`"scan_data"`), skipping the service layer.

**Fix:** a domain enum, `class FileKind(StrEnum): SCAN = "scan"; MASK = "mask"`, or
service methods `get_scan(...)` and `get_mask(...)`.

---

## 4. OOP and SOLID

### 4.1 🟠 Primitive obsession: dicts and strings instead of domain types

Patients, metrics and statuses are passed around as `dict` and `str`:

- the status strings are defined in [patient_service.py:31](app/services/patient_service.py#L31),
  repeated as a `Literal` in [schemas/patient.py:68](app/schemas/patient.py#L68), and
  again in the frontend;
- the dict keys (`"metrics"`, `"segmented"`, `"processing_started_at"`, `"doctor_id"`)
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

### 4.2 🟡 `PatientService` has too many responsibilities (SRP)

**Where:** [app/services/patient_service.py](app/services/patient_service.py), 232 lines

It handles patient CRUD, ownership checks, DICOM preparation, job submission, the job
itself, stale-job detection and ZIP export. These change for different reasons.

**Fix:** split along those reasons:

- `PatientService`: CRUD and ownership;
- `SegmentationService`: `start(patient)`, `run(job)`, `expire_stale()`;
- `ResultExporter`: building the ZIP.

### 4.3 🟡 Services depend on concrete classes (DIP)

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

### 4.4 🟡 Simulation is handled with `if` branches (OCP / polymorphism)

**Where:** [app/ml/inference.py:75](app/ml/inference.py#L75),
[app/ml/inference.py:81](app/ml/inference.py#L81)

`Segmenter` checks `if self._model is None` in several methods, and the
`allow_simulation` decision is made inside its constructor. One class with a null model
inside is acting as two different implementations.

**Fix:** two classes behind the same protocol (`NnUnetSegmenter`, `SimulatedSegmenter`),
with the choice made once at startup in the composition root. Neither class then needs
to know the other exists, and adding a third, for example an ONNX implementation, needs
no changes to existing code.

### 4.5 ⚪ Side effect in a constructor

[app/ml/inference.py:54](app/ml/inference.py#L54) calls `torch.set_num_threads()`, which
changes the setting for the **whole process**. Do it at startup in `create_app`, where
process-wide configuration belongs.

---

## 5. Clean code

### 5.1 🟡 Two sources of truth for the patient's state

`segmented` and `status` describe overlapping facts and are updated separately
([patient_service.py:100](app/services/patient_service.py#L100),
[:120](app/services/patient_service.py#L120),
[:163](app/services/patient_service.py#L163)). Sooner or later they will disagree, for
example `segmented=True` with `status="failed"`. Keep `status` and derive "has a mask"
from the stored files, or from `status == COMPLETED`.

### 5.2 🟡 Repeated "mark failed" code (DRY)

`{"status": FAILED, "segmentation_error": ...}` is written by hand four times
([:159](app/services/patient_service.py#L159), [:192](app/services/patient_service.py#L192),
[:205](app/services/patient_service.py#L205), [:225](app/services/patient_service.py#L225)).
Extract `_mark_failed(patient_id, message)`, or better, `patient.fail(message)` on the
domain object.

### 5.3 🟡 Ambiguous names

| Name | Problem | Suggestion |
|---|---|---|
| `date` | Set at creation **and overwritten on every segmentation** ([:164](app/services/patient_service.py#L164)), so it is neither "created" nor "scan date" | `scan_date` (from DICOM `StudyDate`) and `segmented_at` |
| `filename` | A generated name (`<first file>_16slices.nii.gz`), not the uploaded file | `scan_filename` |
| `file_size` | The size of the converted NIfTI, not the upload | `scan_size_bytes` |
| `artery_detected` | The model's label in `dataset.json` is `"tumor"` | Use the label name from `dataset.json` |
| `coverage` | Share of the whole volume. It depends on the crop size and has no clinical meaning | Remove, or document what it is for |

### 5.4 🟡 Magic threshold in voxels

[app/ml/metrics.py:5](app/ml/metrics.py#L5): `ARTERY_MIN_VOXELS = 50`. The physical volume
of 50 voxels depends on the scan's resolution (50 voxels at 0.4 mm ≈ 3 mm³, at 1 mm =
50 mm³). Define the threshold in **mm³** and compare it with `volume_mm3`.

### 5.5 ⚪ Smaller items

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

## 6. Persistence and storage

### 6.1 🟠 Listing patients downloads their files

**Where:** [app/repositories/patient_repository.py:36-38](app/repositories/patient_repository.py#L36-L38)

`stream()` fetches **whole documents**, including inline base64 files (up to ~680 KB per
file, two per patient), and `_to_dict` then throws them away. A doctor with 50 patients
can transfer tens of MB on every page load, and while a scan is processing this happens
every 5 seconds because of polling.

**Fix:** a projection, `self._collection().where(...).select([...fields...]).stream()`.
The real fix is moving the file data out of the patient document (3.3).

### 6.2 🟠 Naive local datetimes

**Where:** [patient_repository.py:30](app/repositories/patient_repository.py#L30),
[:47](app/repositories/patient_repository.py#L47),
[file_storage.py:74](app/storage/file_storage.py#L74),
[patient_service.py:38](app/services/patient_service.py#L38),
[patient_service.py:46](app/services/patient_service.py#L46)

`datetime.now()` returns local time without a timezone, and the Firestore client
interprets naive datetimes as UTC. On Render the server runs in UTC, so the values are
right. Run the app on a machine in Romania (UTC+2) and every timestamp is off by 2 hours.
The code also mixes three representations: datetime objects, `time.time()` floats
(`processing_started_at`) and `"YYYY-MM-DD"` strings (`date`).

**Fix:** use `datetime.now(timezone.utc)` everywhere, a single representation, and an
injectable clock (`now: Callable[[], datetime]`), so tests can control time instead of
writing `time.time() - 3600`.

### 6.3 🟡 File writes are not atomic

**Where:** [app/storage/file_storage.py:55-75](app/storage/file_storage.py#L55-L75)

`save()` deletes the old chunks, writes the new ones, then updates the metadata, as
separate operations. A download running at the same moment (or a crash in between) can
see half-written chunks, or chunks that don't match the metadata, and return a corrupt
file. The deletes are also one round trip per chunk
([:125-127](app/storage/file_storage.py#L125-L127)).

**Fix:** write the new chunks under a new version (`.../v{n}/chunk_i`), switch the
metadata to that version in one update, then delete the old version. Use
`db.batch()` / `bulk_writer()` for the many small writes and deletes.

### 6.4 🟡 Downloads hold whole files in memory

**Where:** [file_storage.py:77-94](app/storage/file_storage.py#L77-L94),
[api/patients.py:104](app/api/patients.py#L104)

A download keeps the base64 string, the decoded bytes and a `BytesIO` copy in memory at
the same time, next to a ~300 MB model on a 512 MB instance. A few concurrent downloads
of large scans can run out of memory. Fixing 2.1 (compression) reduces this a lot. The
proper solution is object storage with **signed URLs**: the browser downloads straight
from Cloud Storage, and the API never handles the file contents.

### 6.5 🟡 Other data issues

- **No pagination** on `GET /patients`: it returns every patient on each poll. Add
  `limit` and a cursor (`start_after`), plus an explicit order (`created_at desc`).
- **Email uniqueness is not enforced**: two doctor documents with the same email make
  `limit(1)` return either of them at random. Use the normalised email as the document
  id, or check uniqueness inside a transaction when creating an account.
- **Repeated reads**: `build_results_zip` reads the patient document 5 times (one `get`,
  then `get_file` twice, each of which does a `get` plus a `load`). Load the patient
  once and pass it along.

---

## 7. Background jobs and concurrency

### 7.1 🟡 Jobs are not recovered after a restart

**Where:** [app/core/job_queue.py](app/core/job_queue.py)

Every deploy on Render restarts the process. Queued and running jobs are lost, and users
wait `JOB_STALE_AFTER_MINUTES` (20 minutes) before seeing "failed". The scan is already
stored, so the job could simply be **restarted** instead:

- at startup, find patients with `status == "processing"` and queue them again (with a
  new job id, see 2.3);
- on `SIGTERM`, stop accepting new jobs, so that a running job is not cut off without
  being recorded.

Marking stale jobs failed during `GET` requests also means reads write to the database
(a command-query separation violation). Recovery at startup makes most of that code
unnecessary.

### 7.2 🟡 One sync worker serialises all requests

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

### 7.3 ⚪ The queue's capacity is global

`MAX_PENDING_JOBS = 3` is shared by all doctors, so one doctor can fill the queue for
everyone. A per-doctor limit is fairer.

---

## 8. Security

### 8.1 🟠 Responses use a blacklist instead of a whitelist

**Where:** [app/services/auth_service.py:17-18](app/services/auth_service.py#L17-L18),
[app/api/auth.py:18-22](app/api/auth.py#L18-L22),
[app/api/patients.py:65](app/api/patients.py#L65)

- `login` and `/me` return the whole doctor document except `password`. Any field added
  to that document later (`reset_token`, `is_admin`, `phone`, …) is sent to the client
  automatically.
- `PUT /patients/<id>` returns the raw repository dict: `doctor_id`,
  `processing_started_at`, file sizes, timestamps. Every other endpoint uses
  `PatientSummary` / `PatientDetail`.

**Fix:** response schemas everywhere (`DoctorOut(id, name, email)`, and
`PatientDetail` for `PUT`). A whitelist cannot leak fields by accident.

### 8.2 🟡 Tokens stay valid after a password change or account removal

**Where:** [app/core/security.py:65-72](app/core/security.py#L65-L72)

The JWT is checked only for its signature and expiry. After a password change (for
example after a compromise), old tokens keep working for up to 8 hours. A deleted doctor
can still call the patient endpoints, and `/me` then returns `404` where `401` would be
right ([auth_service.py:41-45](app/services/auth_service.py#L41-L45)).

**Fix:** store `password_changed_at` (or a `token_version`) on the doctor and reject
tokens issued before it. Short-lived access tokens with refresh tokens are the standard
way to keep this check cheap.

### 8.3 🟡 Other items

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

## 9. ML pipeline

### 9.1 🟠 DICOM series are not validated

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

### 9.2 🟡 Files are filtered by extension

[dicom_converter.py:58](app/ml/dicom_converter.py#L58) skips files that don't end in
`.dcm`. Many PACS and CD exports have **no extension** (`IM000001`). Detect DICOM by
content instead: the `DICM` marker at byte 128, or simply try `pydicom.dcmread`.

### 9.3 🟡 The network architecture is hard-coded

[model_loader.py:72-93](app/ml/model_loader.py#L72-L93) hard-codes `PlainConvUNet`,
`Conv2d`, `InstanceNorm2d` and `LeakyReLU`. But `plans.json` names the network class and
its operations (`architecture.network_class_name`, `_kw_requires_import`). If the model
is retrained with another nnU-Net configuration (for example ResEnc), loading fails,
which is the better case. In the worse case, a model is built that does not match its
weights. Read the class and its operations from the plans (nnU-Net's own
`get_network_from_plans` does exactly this), or at least check that the plans contain
what the code assumes.

### 9.4 🟡 Inference is not reproducible or traceable

A result does not record **which** model produced it. Store a `model_version` (for
example the checkpoint's SHA-256 and the nnU-Net fold) together with the metrics. When
the model is retrained, you can then tell which results came from which version. That is
essential for any medical or research use.

### 9.5 ⚪ Smaller items

- DICOM direction cosines (`ImageOrientationPatient`) are ignored and all slices are
  assumed axial. This is already documented as a limitation. Reject non-axial series
  explicitly rather than processing them wrongly.
- `simulate_segmentation` returns a `(1, 1, 1)` mask when anything fails
  ([simulation.py:36-38](app/ml/simulation.py#L36-L38)). It is development-only code, but
  it could just raise.

---

## 10. API design

### 10.1 🟡 Response shapes are inconsistent

| Endpoint | Returns |
|---|---|
| `POST /patients/` | `{"message", "patient": Summary}` |
| `POST /patients/<id>/upload-dicom` | `{"message", "result": {"status"}}` |
| `POST /patients/<id>/re-segment` | `{"message", "patient": Detail}` |
| `PUT /patients/<id>` | `{"message", "patient": raw dict}` |

A client has to know each shape separately. Return the same patient representation from
every endpoint that changes a patient. The `message` fields are UI text, so the frontend
should own them.

### 10.2 ⚪ Resource-oriented URLs

`/upload-dicom` and `/re-segment` are verbs, and `/download` is a legacy alias
([patients.py:84](app/api/patients.py#L84)). A more RESTful layout:

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

### 10.3 ⚪ The health check says nothing about readiness

[health.py](app/api/health.py) always returns `healthy`. Report what actually matters:
whether the model is loaded (`is_model_loaded`), the queue length, and whether Firestore
is reachable. Use two endpoints: `/health/live` (the process is up) and `/health/ready`
(the app can serve requests).

---

## 11. Testing and tooling

### 11.1 🟡 No CI

There is no `.github/workflows`, so nothing runs `ruff` and `pytest` on push. Without CI,
tests are optional, and over time they stop passing. Add a workflow:

```yaml
# .github/workflows/backend.yml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: backend } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check .
      - run: pytest
```

### 11.2 🟡 No type checker

The code has type hints, but nothing checks them. Add `mypy` (or `pyright`) in strict
mode for `app/`. It would have flagged the untyped providers (4.3), and together with
domain types (4.1) it catches the typos that dict keys allow.

### 11.3 🟡 Tests patch private attributes

[tests/conftest.py](tests/conftest.py) monkeypatches `patient_service._segmenter_provider`,
`auth_service.doctors.get_by_email`, and so on. These tests depend on implementation
details: renaming a private attribute breaks them although the behaviour is unchanged.
With constructor injection (3.2 / 4.3) the tests build the service with fakes instead.

### 11.4 🟡 Missing kinds of tests

- **Firestore emulator tests** for the repositories and storage. The current
  `FakeFirestore` only imitates the API, so it cannot catch real Firestore behaviour
  (for example subcollections surviving their parent, bug 2.2).
- **Round-trip tests with real tools**: a downloaded file must open with `nibabel.load`
  (bug 2.1).
- **A regression test for the model**: one small real CT crop with its ground-truth
  label, asserting a minimum Dice. It catches preprocessing regressions such as the
  orientation, HU and resampling bugs fixed earlier.
- A coverage report (`pytest --cov`), so that untested code is visible.

### 11.5 ⚪ Inconsistent Python versions

Render uses 3.11, local tests ran on 3.10, and `pyproject.toml` targets `py310`. Pin one
version everywhere (`.python-version`, `render.yaml`, the CI workflow, ruff's
`target-version`).

---

## 12. Operations

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

## 13. What is already good

These are worth pointing out in an interview.

- **A clear layered architecture**, with the ML package independent of Flask and
  Firebase.
- **An application factory** with configuration per environment, and a production
  start that refuses to run without `SECRET_KEY` or a model.
- **Typed application exceptions** mapped to HTTP status codes in one place. Unexpected
  errors are logged and never leaked to clients.
- **Authentication and authorization**: JWT, bcrypt with transparent migration of the
  legacy hashes, the same error for an unknown email and a wrong password (and the same
  response time), and ownership checks that answer `404` for another doctor's patients.
- **Input validation with Pydantic** at the API boundary.
- **A faithful re-implementation of nnU-Net's 2D inference** (HU conversion,
  orientation, resampling, Gaussian sliding window, mirroring), tested against stub
  networks, including a test that fails when the orientation is wrong.
- **Background processing** with a bounded queue, an explicit status machine, and
  failures recorded instead of silently replaced by fake results.
- **~95 tests** that run in seconds without credentials, a GPU or a network connection.

---

## 14. Suggested order of work

| Priority | Item | Effort |
|---|---|---|
| 1 | 2.1 Gzip-compress NIfTI files (+ a test that opens a downloaded file) | 30 min |
| 2 | 2.4 Normalise emails | 15 min |
| 3 | 2.5 and 8.1 Whitelist responses, no internal messages | 45 min |
| 4 | 2.2 and 2.3 Job id plus "refuse delete while processing" | 1–2 h |
| 5 | 6.1 Firestore projection for listing patients | 15 min |
| 6 | 6.2 UTC datetimes and an injectable clock | 1 h |
| 7 | 11.1 CI workflow | 30 min |
| 8 | 3.1, 3.2, 4.3 Settings in constructors, composition root, protocols | half a day |
| 9 | 4.1 `Patient` domain model and `PatientStatus` enum | half a day |
| 10 | 3.3 and 6.x Files in their own collection, then Cloud Storage with signed URLs | 1 day |
| 11 | 7.1 and 7.2 Job recovery at startup, threaded workers with a transactional claim | 1 day |
| 12 | 9.1–9.4 DICOM series validation, architecture from plans, model versioning | 1 day |

Items 1–7 are small, independent fixes. Items 8–9 are the refactoring that makes the
code base clearly "senior". Items 10–12 are what a production deployment would need.
