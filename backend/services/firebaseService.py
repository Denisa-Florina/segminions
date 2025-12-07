import firebase_admin
from firebase_admin import credentials, firestore
import os
from datetime import datetime
import hashlib
import base64
import json

# Initialize Firebase Admin SDK
service_account_path = os.environ.get(
    'FIREBASE_SERVICE_ACCOUNT_PATH',
    'backend/serviceAccountKey.json'
)

if not firebase_admin._apps:
    service_account_info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_PATH"])
    cred = credentials.Certificate(service_account_info)

# Get Firestore reference
db = firestore.client()


class FirebaseService:
    """Service for Firebase Firestore operations (Database only - no Storage)"""
    
    # ============================================
    # DOCTOR OPERATIONS
    # ============================================
    
    @staticmethod
    def get_doctor_by_email(email):
        """Get doctor by email from Firestore"""
        try:
            docs = db.collection('doctors').where('email', '==', email).limit(1).stream()
            for doc in docs:
                return {'id': doc.id, **doc.to_dict()}
            return None
        except Exception as e:
            print(f"Error getting doctor: {e}")
            return None
    
    @staticmethod
    def get_doctor_by_id(doctor_id):
        """Get doctor by ID from Firestore"""
        try:
            doc = db.collection('doctors').document(doctor_id).get()
            if doc.exists:
                return {'id': doc.id, **doc.to_dict()}
            return None
        except Exception as e:
            print(f"Error getting doctor: {e}")
            return None
    
    @staticmethod
    def create_doctor(doctor_data):
        """Create a new doctor in Firestore"""
        try:
            # Hash the password before storing
            if 'password' in doctor_data:
                doctor_data['password'] = hashlib.sha256(
                    doctor_data['password'].encode()
                ).hexdigest()
            
            doctor_data['created_at'] = datetime.now()
            doc_ref = db.collection('doctors').document()
            doc_ref.set(doctor_data)
            return {'id': doc_ref.id, **doctor_data}
        except Exception as e:
            print(f"Error creating doctor: {e}")
            return None
    
    @staticmethod
    def update_doctor(doctor_id, updates):
        """Update doctor in Firestore"""
        try:
            updates['updated_at'] = datetime.now()
            db.collection('doctors').document(doctor_id).update(updates)
            return FirebaseService.get_doctor_by_id(doctor_id)
        except Exception as e:
            print(f"Error updating doctor: {e}")
            return None
    
    # ============================================
    # PATIENT OPERATIONS
    # ============================================
    
    @staticmethod
    def add_patient(patient_data):
        """Add a new patient to Firestore"""
        try:
            patient_data['created_at'] = datetime.now()
            patient_data['updated_at'] = datetime.now()
            
            doc_ref = db.collection('patients').document()
            doc_ref.set(patient_data)
            
            return {'id': doc_ref.id, **patient_data}
        except Exception as e:
            print(f"Error adding patient: {e}")
            return None
    
    @staticmethod
    def get_patients_by_doctor(doctor_id):
        """Get all patients for a specific doctor (without file data to reduce size)"""
        try:
            patients = []
            docs = db.collection('patients').where('doctor_id', '==', str(doctor_id)).stream()
            
            for doc in docs:
                patient_data = doc.to_dict()
                
                # Don't include file_data in list view (too large)
                if 'file_data' in patient_data:
                    patient_data.pop('file_data')
                
                # Convert Firestore timestamp to string
                if 'created_at' in patient_data:
                    patient_data['created_at'] = patient_data['created_at'].isoformat() if hasattr(patient_data['created_at'], 'isoformat') else str(patient_data['created_at'])
                if 'updated_at' in patient_data:
                    patient_data['updated_at'] = patient_data['updated_at'].isoformat() if hasattr(patient_data['updated_at'], 'isoformat') else str(patient_data['updated_at'])
                
                patients.append({'id': doc.id, **patient_data})
            
            return patients
        except Exception as e:
            print(f"Error getting patients: {e}")
            return []
    
    @staticmethod
    def get_patient_by_id(patient_id, include_file=False):
        """Get a specific patient by ID"""
        try:
            doc = db.collection('patients').document(patient_id).get()
            if doc.exists:
                patient_data = doc.to_dict()
                
                # Option to exclude file data (for performance)
                if not include_file and 'file_data' in patient_data:
                    patient_data.pop('file_data')
                
                # Convert timestamps
                if 'created_at' in patient_data:
                    patient_data['created_at'] = patient_data['created_at'].isoformat() if hasattr(patient_data['created_at'], 'isoformat') else str(patient_data['created_at'])
                if 'updated_at' in patient_data:
                    patient_data['updated_at'] = patient_data['updated_at'].isoformat() if hasattr(patient_data['updated_at'], 'isoformat') else str(patient_data['updated_at'])
                
                return {'id': doc.id, **patient_data}
            return None
        except Exception as e:
            print(f"Error getting patient: {e}")
            return None
    
    @staticmethod
    def update_patient(patient_id, updates):
        """Update patient in Firestore"""
        try:
            updates['updated_at'] = datetime.now()
            db.collection('patients').document(patient_id).update(updates)
            return FirebaseService.get_patient_by_id(patient_id)
        except Exception as e:
            print(f"Error updating patient: {e}")
            return None
    
    @staticmethod
    def delete_patient(patient_id):
        """Delete patient from Firestore"""
        try:
            db.collection('patients').document(patient_id).delete()
            return True
        except Exception as e:
            print(f"Error deleting patient: {e}")
            return False
    
    # ============================================
    # FILE OPERATIONS (Base64 in Database)
    # ============================================
    
    @staticmethod
    def save_file_to_patient(patient_id, file_data, filename):
        """
        Save file as base64 in patient document
        Note: Firestore has a 1MB limit per document, so large files need special handling
        """
        try:
            # Convert file to base64
            file_data.seek(0)
            file_bytes = file_data.read()
            file_base64 = base64.b64encode(file_bytes).decode('utf-8')
            
            # Calculate size
            file_size = len(file_bytes)
            file_size_mb = file_size / (1024 * 1024)
            
            print(f"File size: {file_size_mb:.2f} MB")
            
            # Firestore document limit is 1MB
            # If file is too large, we'll split it into chunks
            if file_size_mb > 0.9:  # Leave some room for other fields
                return FirebaseService._save_large_file(patient_id, file_base64, filename, file_size)
            
            # Small file - save directly in patient document
            updates = {
                'file_data': file_base64,
                'filename': filename,
                'file_size': file_size,
                'updated_at': datetime.now()
            }
            
            db.collection('patients').document(patient_id).update(updates)
            return True
            
        except Exception as e:
            print(f"Error saving file: {e}")
            return False
    
    @staticmethod
    def _save_large_file(patient_id, file_base64, filename, file_size):
        """
        Save large files by splitting into chunks in a subcollection
        """
        try:
            # Split file into chunks (800KB per chunk to be safe)
            chunk_size = 800 * 1024  # 800KB in base64 characters
            chunks = [file_base64[i:i+chunk_size] for i in range(0, len(file_base64), chunk_size)]
            
            # Save chunks to subcollection
            chunks_ref = db.collection('patients').document(patient_id).collection('file_chunks')
            
            # Delete old chunks
            old_chunks = chunks_ref.stream()
            for chunk in old_chunks:
                chunk.reference.delete()
            
            # Save new chunks
            for i, chunk_data in enumerate(chunks):
                chunks_ref.document(f'chunk_{i}').set({
                    'data': chunk_data,
                    'order': i,
                    'created_at': datetime.now()
                })
            
            # Update patient document with metadata
            updates = {
                'filename': filename,
                'file_size': file_size,
                'file_chunks_count': len(chunks),
                'is_chunked': True,
                'updated_at': datetime.now()
            }
            
            db.collection('patients').document(patient_id).update(updates)
            return True
            
        except Exception as e:
            print(f"Error saving large file: {e}")
            return False
    
    @staticmethod
    def get_file_from_patient(patient_id):
        """
        Retrieve file data from patient document
        """
        try:
            patient = FirebaseService.get_patient_by_id(patient_id, include_file=True)
            
            if not patient:
                return None
            
            # Check if file is chunked
            if patient.get('is_chunked', False):
                return FirebaseService._get_large_file(patient_id, patient.get('file_chunks_count', 0))
            
            # Small file - return directly
            if 'file_data' in patient:
                file_bytes = base64.b64decode(patient['file_data'])
                return {
                    'data': file_bytes,
                    'filename': patient.get('filename', 'file.nii.gz'),
                    'size': patient.get('file_size', 0)
                }
            
            return None
            
        except Exception as e:
            print(f"Error getting file: {e}")
            return None
    
    @staticmethod
    def _get_large_file(patient_id, chunks_count):
        """
        Retrieve large file from chunks
        """
        try:
            chunks_ref = db.collection('patients').document(patient_id).collection('file_chunks')
            
            # Get all chunks ordered
            chunks = chunks_ref.order_by('order').stream()
            
            # Reconstruct file
            file_base64 = ''
            for chunk in chunks:
                chunk_data = chunk.to_dict()
                file_base64 += chunk_data['data']
            
            # Decode
            file_bytes = base64.b64decode(file_base64)
            
            # Get metadata
            patient = FirebaseService.get_patient_by_id(patient_id, include_file=False)
            
            return {
                'data': file_bytes,
                'filename': patient.get('filename', 'file.nii.gz'),
                'size': patient.get('file_size', 0)
            }
            
        except Exception as e:
            print(f"Error getting large file: {e}")
            return None


firebase_service = FirebaseService()