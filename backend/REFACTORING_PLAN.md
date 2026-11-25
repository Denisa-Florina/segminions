# MedSeg AI – Backend: Code Review & Plan de Refactorizare

Review făcut din perspectiva unui senior developer. Problemele sunt ordonate după prioritate.

---

## Cuprins

1. [Arhitectura](#1-arhitectura)
2. [Securitate](#2--critic-securitate)
3. [Integritatea rezultatelor AI](#3--critic-integritatea-rezultatelor-ai)
4. [Design și scalare](#4--important-design-și-scalare)
5. [Curățenie](#5--curățenie)
6. [Plan de acțiune](#6-plan-de-acțiune)

---

## 1. Arhitectura

### Structura actuală

```
backend/
  app.py                   ← importă și "services.x", și "backend.services.x", plus un hack cu sys.path
  api/routes/              ← lipsesc fișierele __init__.py
  services/
    authService.py         ← numele în camelCase nu respectă convenția Python (PEP 8 cere snake_case)
    firebaseService.py     ← conexiunea la DB, accesul la date și stocarea fișierelor, toate amestecate
    segmentationService.py ← 560 de linii: DICOM, preprocesare, inferență, metrici, simulare și logică de business
  models/nnunet/           ← "models" se confundă cu modelele de date; checkpoint-ul de 60MB e pus direct în git
```

### Probleme

- **Importurile sunt inconsecvente:** `services.firebaseService` în `app.py`, dar `backend.services...` în rest. Merg doar datorită hack-ului `sys.path.insert`.
- **Căile sunt relative la directorul curent** (`'backend/models/nnunet'`, `'backend/serviceAccountKey.json'`). Dacă aplicația pornește din `backend/`, modelul **nu se găsește** și aplicația trece în simulation mode fără niciun avertisment.
  → Căile trebuie construite relativ la fișier: `Path(__file__).resolve().parent / ...`
- **Responsabilitățile sunt amestecate:** rutele, logica de business și accesul la DB sunt în aceleași fișiere.
- **Checkpoint-ul modelului (60MB) e în git.** Trebuie mutat în Git LFS sau descărcat la build.

### Structura propusă

```
backend/
├── app/
│   ├── __init__.py            # create_app() – application factory
│   ├── config.py              # Config din variabile de mediu (Dev/Prod), fără valori implicite pentru secrete
│   ├── extensions.py          # inițializare Firebase și CORS
│   ├── api/                   # DOAR HTTP: parsează request-ul, apelează serviciul, întoarce răspunsul
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── patients.py
│   │   └── health.py
│   ├── core/
│   │   ├── security.py        # decoratorul @login_required și current_doctor
│   │   └── errors.py          # excepții proprii și error handlers globale
│   ├── schemas/
│   │   └── patient.py         # validare input și serializare output (pydantic / marshmallow)
│   ├── services/              # logica de business
│   │   ├── auth_service.py
│   │   └── patient_service.py # orchestrează: creează pacientul, rulează segmentarea, salvează
│   ├── repositories/          # DOAR acces la date (Firestore)
│   │   ├── doctor_repository.py
│   │   └── patient_repository.py
│   ├── storage/
│   │   └── file_storage.py    # Firebase Cloud Storage pentru fișierele .nii.gz
│   └── ml/                    # partea de AI, independentă de Flask
│       ├── dicom_converter.py
│       ├── preprocessing.py
│       ├── model_loader.py
│       ├── inference.py
│       └── metrics.py
├── ml_weights/nnunet/         # descărcat la build sau Git LFS, nu pus direct în git
├── tests/
│   ├── test_auth.py
│   ├── test_patients.py
│   └── test_dicom_converter.py
├── wsgi.py                    # from app import create_app; app = create_app()
├── requirements.txt
├── requirements-dev.txt       # pytest, ruff
├── .env.example               # lista variabilelor de mediu, fără valori
└── README.md                  # cum pornești proiectul, arhitectura, limitările
```

**Principiul:** layered architecture, adică `api → services → repositories / ml`. Fiecare strat are o singură responsabilitate, iar partea de ML se poate testa fără Flask și fără Firebase.

---

## 2. 🔴 Critic: Securitate

Aplicația lucrează cu date medicale, deci securitatea are prioritate maximă.

### 2.1 Nu există autorizare (IDOR)

Orice persoană care cunoaște un `patient_id` poate citi, modifica, șterge sau descărca datele oricărui pacient. Endpoint-urile acceptă și `doctor_id` trimis de client (`api/routes/patientRoutes.py`, liniile 12 și 56), deci un utilizator se poate da drept alt doctor.

**Soluție:**
- Un decorator `@login_required` care ia identitatea doctorului **de pe server** (din token sau sesiune), nu din request.
- Fiecare operație pe un pacient verifică `patient.doctor_id == current_doctor.id`. Altfel răspunsul e `403` (sau `404`).

### 2.2 Autentificarea

- Parolele sunt hash-uite cu **SHA-256 fără salt** (`services/authService.py:15`). E nesigur. Trebuie **bcrypt** sau **argon2**. `passlib` e deja în requirements, dar nu e folosit.
- **User enumeration:** mesajele „Doctor not found” și „Invalid password” sunt diferite, deci un atacator poate afla ce emailuri există. Trebuie un singur mesaj: „Invalid credentials”.
- **Cookie-ul de sesiune nu ajunge cross-site.** Frontend-ul e pe `medsegai.web.app`, backend-ul pe `onrender.com`. Probabil de aceea `doctor_id` e trimis din frontend.

✅ **Recomandare:** **Firebase Authentication**. Frontend-ul are deja configurația Firebase.
- Clientul trimite `Authorization: Bearer <idToken>`.
- Backend-ul îl verifică cu `firebase_admin.auth.verify_id_token()`.
- Asta rezolvă dintr-o dată hash-uirea parolelor, sesiunile și CORS-ul cu cookies.

### 2.3 Bug la login

`api/routes/authRoutes.py`, liniile 20–21:

```python
doctor, error = AuthService.authenticate_doctor(email, password)
current_app.logger.info(f"Received login doctor: {doctor}")
current_app.logger.info(f"Received login id: {doctor['id']}")   # ← doctor e None la parolă greșită
if error:
    return jsonify({'error': error}), 401
```

`doctor['id']` e accesat **înainte** de verificarea `if error`. La o parolă greșită `doctor` e `None`, se aruncă `TypeError` și răspunsul e **500** în loc de 401. În plus, se loghează datele doctorului.

### 2.4 Alte probleme de securitate

| Problemă | Unde | Soluție |
|---|---|---|
| `SECRET_KEY` are o valoare implicită hardcodată | `app.py:16` | În producție, aplicația refuză pornirea dacă variabila lipsește |
| `return jsonify({'error': str(e)}), 500` expune detalii interne | peste tot în rute | Error handler global: loghează excepția, întoarce un mesaj generic |
| Originul CORS `'https://medsegai.web.app/'` are `/` la final, deci nu se potrivește niciodată | `app.py:24` | Fără slash final |
| Upload-ul nu are limită de număr de fișiere și verifică doar extensia `.dcm` | `patientRoutes.py` | Limită de fișiere și validare reală (pydicom citește headerul) |

---

## 3. 🔴 Critic: Integritatea rezultatelor AI

Acesta e cel mai probabil subiect de întrebări la un interviu.

### 3.1 Confidence-ul e fals

`services/segmentationService.py`, liniile 407–412:

```python
if voxel_count > 0:
    confidence = 0.6                                         # hardcodat
else:
    confidence = round(0.3 + np.random.random() * 0.15, 2)   # random
```

În simulare, `dice_score` și `iou_score` sunt tot random (liniile 504–510). Într-o aplicație medicală, metricile inventate afișate unui doctor sunt un semnal foarte rău.

**Soluție:**
- Confidence-ul real se calculează așa: aplici `softmax` pe output-ul modelului, apoi faci media probabilităților pe voxelii clasificați ca foreground.
- Dice și IoU **nu se pot calcula** la inferență, pentru că nu există ground truth. Trebuie scoase din răspuns.

### 3.2 Fallback-ul în simulare e silențios

Dacă modelul nu se încarcă sau dă eroare, aplicația desenează un cub în centrul volumului și îl prezintă ca rezultat real.

**Soluție:** fie întoarce eroare, fie salvează explicit `simulated: true` și afișează clar asta în UI.

### 3.3 Preprocesare incorectă

- **Nu se aplică `RescaleSlope` / `RescaleIntercept`** din DICOM, deci valorile **nu sunt în HU**. Normalizarea folosește însă percentile în HU (−340 … 529).
  ```python
  hu = pixel_array * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
  ```
- **Fiecare slice e redimensionat la `patch_size`.** nnU-Net nu funcționează așa: face resampling la spacing-ul țintă, apoi inferență cu sliding window.
  → `nnunetv2` e deja instalat, deci se poate folosi direct `nnUNetPredictor` în loc de o reimplementare manuală.
- **Bug la un singur fișier DICOM:** `img_array[np.newaxis, :, :]` produce forma `(1, H, W)`, dar bucla de inferență iterează pe ultima axă. Pentru o singură imagine rezultă W „slice-uri” greșite. Trebuie `img_array[:, :, np.newaxis]`.

### 3.4 Întârzieri artificiale

`time.sleep(1.0)` (linia 116) și `time.sleep(1.5)` (linia 171) încetinesc fiecare request. Trebuie șterse.

---

## 4. 🟠 Important: Design și scalare

### 4.1 Fișierele sunt stocate ca base64 în Firestore

- Base64 adaugă ~33% la dimensiune, iar Firestore nu e făcut pentru fișiere (limita e 1MB per document, de aceea există mecanismul cu chunks).
- **Soluție:** fișierele merg în **Firebase Cloud Storage**, iar în document se salvează doar calea (`scans/{patient_id}/scan.nii.gz`).

**Bug legat de asta:** `delete_patient` șterge documentul, dar **nu și subcolecțiile** `scan_data_chunks` / `mask_data_chunks`. Firestore nu șterge în cascadă, deci datele medicale rămân orfane în bază (o problemă și din perspectiva GDPR).

### 4.2 Inferența rulează sincron în request

Gunicorn are implicit timeout de 30s și 1 worker sync. Un CT mare dă timeout.

**Soluție:**
1. `POST /patients` întoarce `202 Accepted` cu `status: "processing"`.
2. Segmentarea rulează ca background job (Cloud Tasks / Celery / RQ).
3. Frontend-ul face polling (sau ascultă pe Firestore realtime) până la `status: "completed"`.

Câmpul `status: 'processing'` există deja în cod.

### 4.3 Duplicare

- Transformarea pacient → JSON apare de 3 ori în `patientRoutes.py`.
- Conversia `created_at` / `updated_at` apare de 2 ori în `firebaseService.py`.
- Codul de download (scan / mask) e aproape identic.

→ Locul ei e într-un schema/serializer (`schemas/patient.py`) și în funcții helper.

### 4.4 Logging

Tot logging-ul e făcut cu `print()`. Trebuie înlocuit cu modulul `logging` (`logging.getLogger(__name__)`), cu niveluri (`info`, `warning`, `error`). Nu se loghează date personale (nume de pacienți, emailuri).

### 4.5 Erori înghițite

Fiecare metodă din `FirebaseService` face:

```python
except Exception as e:
    print(f"Error ...: {e}")
    return None
```

Pentru apelant, „nu există” și „DB-ul a picat” arată la fel.

**Soluție:** excepțiile se propagă, iar error handler-ul global le transformă în `404` / `500`. Se pot defini excepții proprii (`NotFoundError`, `ForbiddenError`, `ValidationError`) în `core/errors.py`.

---

## 5. 🟡 Curățenie

Rapid de făcut, contează la prima impresie.

- **Importuri nefolosite:**
  - `app.py`: `hashlib`, `datetime`
  - `segmentationService.py`: `tempfile`, `SimpleITK`, `Path`, `time` (după ce scoți `sleep`)
- **Dependențe nefolosite** în `requirements.txt`: `python-jose`, `passlib` (până îl folosești), `SimpleITK`, `Pillow`.
- **Versiuni nefixate:** `torch>=2.0.0`, `nnunetv2`, `dynamic-network-architectures`, `SimpleITK`, `scipy`. Trebuie fixate pe versiuni exacte pentru build-uri reproductibile.
- **Cod mort:**
  - `UPLOAD_FOLDER` e creat, dar nu e folosit.
  - `AuthService.validate_session` și `AuthService.logout_doctor` nu fac nimic util.
  - `transformed_patient['status']` are valori diferite (`'processing'` / `'pending'`) în endpoint-uri diferite.
- **Lipsesc:**
  - `.env.example` cu toate variabilele (`SECRET_KEY`, `FRONTEND_URL`, `FIREBASE_SERVICE_ACCOUNT_JSON`, ...)
  - **Teste.** Chiar și 5–6 teste cu pytest ajung pentru început:
    - login cu credențiale corecte → 200
    - login cu parolă greșită → 401 (nu 500!)
    - acces la pacientul altui doctor → 403
    - conversie DICOM → NIfTI pe un fișier mic de test
  - Un linter/formatter (`ruff`).
- **Mesajele de commit** („fix confidence”, „Edit view”) ar trebui să fie descriptive (de exemplu „Compute confidence from softmax probabilities”).

---

## 6. Plan de acțiune

| # | Pas | Efort |
|---|---|---|
| 1 | Verifică în logurile Render dacă scrie `[OK] nnUNet model loaded` sau `Using simulation mode` | 5 min |
| 2 | Fixează bug-ul de la login, scoate `time.sleep`, metricile random și `str(e)` din răspunsuri | ~1 oră |
| 3 | Adaugă autorizare: `@login_required` și verificarea de ownership (ideal cu Firebase Auth) | ~0.5–1 zi |
| 4 | Reorganizează folderele după structura propusă, adaugă `.env.example` și câteva teste | ~1 zi |
| 5 | Cloud Storage în loc de base64 în Firestore și curățarea fișierelor la ștergere | ~0.5 zi |
| 6 | Background jobs pentru segmentare | ~1 zi |
| 7 | `nnUNetPredictor` în loc de preprocesarea manuală, confidence real din softmax | ~1 zi |

### Known limitations / Next steps (de menționat la interviu)

Dacă nu ajungi să implementezi totul, poți prezenta punctele 5–7 ca limitări cunoscute, cu un plan pentru fiecare. Un intervievator apreciază mult un candidat care își știe limitele aplicației.

- Fișierele medicale sunt stocate în Firestore. Planul: migrare în Cloud Storage.
- Segmentarea e sincronă. Planul: coadă de job-uri și status `processing` / `completed`.
- Preprocesarea e o reimplementare simplificată a nnU-Net. Planul: `nnUNetPredictor` cu sliding window și resampling.
- Aplicația nu e validată clinic. E un prototip de cercetare, nu un dispozitiv medical.
