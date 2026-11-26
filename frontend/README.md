# MedSeg AI – Frontend

React app for doctors: log in, manage patients, upload CT scans (DICOM) and download the
AI segmentation. Talks to the Flask backend in `../backend`.

## Running locally

```bash
npm install
npm start            # http://localhost:3000
```

By default the app calls the backend at `http://127.0.0.1:5001/api`. To use another
backend, set `REACT_APP_API_URL` in `.env.local` (development) or
`.env.production.local` (production builds), e.g.:

```
REACT_APP_API_URL=https://medsegai.onrender.com/api
```

## Deploying (Firebase Hosting)

```bash
npm run build                     # uses .env.production.local
firebase deploy --only hosting    # project "medsegai", see .firebaserc
```

Check that the build points to the right backend before deploying: the API URL is
baked into the bundle at build time.

## Structure

```
src/
├── components/
│   ├── auth/          LoginScreen
│   ├── dashboard/     Dashboard (state, polling), DashboardView, Sidebar
│   ├── patients/      PatientsView, PatientProfile, AddPatientModal,
│   │                  StatusBadge, ConfidenceValue
│   └── settings/      SettingsView
├── contexts/          AuthContext (logged-in doctor)
└── services/          api (axios + JWT header), authService, patientService
```

## How it talks to the backend

- **Authentication:** login returns a JWT, stored in `localStorage` and sent as
  `Authorization: Bearer <token>` on every request. A `401` logs the user out.
- **Segmentation is asynchronous:** an upload returns immediately with status
  `processing`; the patient page and the list poll until it becomes `completed` or
  `failed`.
- **Simulated results** (when the backend runs without the AI model) are shown with a
  warning badge instead of a confidence value.
