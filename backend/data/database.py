"""
Data Layer - Mock Database
In production, replace this with SQLAlchemy models and PostgreSQL/MySQL
"""

class MockDatabase:
    def __init__(self):
        self.doctors = [
            {
                'id': 1,
                'email': 'dr.popescu@hospital.ro',
                'password': 'password123',
                'name': 'Dr. Ion Popescu',
                'specialization': 'Radiologie',
                'hospital': 'Spitalul Județean Cluj'
            },
            {
                'id': 2,
                'email': 'dr.ionescu@hospital.ro',
                'password': 'password123',
                'name': 'Dr. Maria Ionescu',
                'specialization': 'ORL',
                'hospital': 'Spitalul Clinic Cluj'
            }
        ]

        self.patients = [
            {
                'id': 1,
                'name': 'Vasile Mureșan',
                'age': 45,
                'date': '2025-10-28',
                'dicom_file': 'CT_Scan_001.dcm',
                'doctor_id': 1,
                'segmented': True,
                'metrics': {
                    'confidence': 0.92,
                    'dice_score': 0.88,
                    'iou_score': 0.82
                }
            },
            {
                'id': 2,
                'name': 'Elena Pop',
                'age': 52,
                'date': '2025-10-27',
                'dicom_file': 'CT_Scan_002.dcm',
                'doctor_id': 1,
                'segmented': True,
                'metrics': {
                    'confidence': 0.87,
                    'dice_score': 0.85,
                    'iou_score': 0.78
                }
            }
        ]

    def get_doctor_by_email(self, email):
        return next((d for d in self.doctors if d['email'] == email), None)

    def get_patients_by_doctor(self, doctor_id):
        return [p for p in self.patients if p['doctor_id'] == doctor_id]

    def get_patient_by_id(self, patient_id):
        return next((p for p in self.patients if p['id'] == patient_id), None)

    def add_patient(self, patient_data):
        new_id = max([p['id'] for p in self.patients], default=0) + 1
        patient = {**patient_data, 'id': new_id}
        self.patients.append(patient)
        return patient

    def update_patient(self, patient_id, updates):
        for i, patient in enumerate(self.patients):
            if patient['id'] == patient_id:
                self.patients[i] = {**patient, **updates}
                return self.patients[i]
        return None

    def delete_patient(self, patient_id):
        self.patients = [p for p in self.patients if p['id'] != patient_id]
        return True


db = MockDatabase()