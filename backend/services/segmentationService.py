import numpy as np
import time
from datetime import datetime
from backend.services.firebaseService import firebase_service

class SegmentationService:
    def __init__(self):
        self.model_loaded = True

    def process_dicom(self, dicom_file, patient_data, doctor_id):
        """Process initial DICOM/NIFTI file when creating a patient"""
        time.sleep(0.5)  # simulate processing delay
        
        filename = getattr(dicom_file, 'filename', 'scan.nii.gz')
        
        # Get file size
        dicom_file.seek(0, 2)  # end
        file_size = dicom_file.tell()
        dicom_file.seek(0)  # start
        
        # Simulate segmentation metrics
        metrics = self._simulate_segmentation()
        
        patient = {
            'name': patient_data['name'],
            'age': patient_data['age'],
            'filename': filename,
            'file_size': file_size,
            'doctor_id': str(doctor_id),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'segmented': True,
            'metrics': metrics
        }
        
        # Create patient in Firebase
        created_patient = firebase_service.add_patient(patient)
        
        if created_patient and 'id' in created_patient:
            # Save DICOM/NIFTI file
            success = firebase_service.save_file_to_patient(
                created_patient['id'],
                dicom_file,
                filename
            )
            if not success:
                print("Warning: File upload failed, but patient created.")
        
        return created_patient

    def process_uploaded_dicom(self, dicom_file, patient_id):
        """Process uploaded DICOM/NIFTI file for existing patient"""
        time.sleep(1.0)  # simulate processing
        
        filename = getattr(dicom_file, 'filename', 'scan.nii.gz')
        
        dicom_file.seek(0, 2)
        file_size = dicom_file.tell()
        dicom_file.seek(0)
        
        success = firebase_service.save_file_to_patient(patient_id, dicom_file, filename)
        if not success:
            raise Exception("Failed to upload file")
        
        metrics = self._simulate_segmentation()
        
        updates = {
            'filename': filename,
            'file_size': file_size,
            'metrics': metrics,
            'segmented': True,
            'date': datetime.now().strftime('%Y-%m-%d')
        }
        
        firebase_service.update_patient(patient_id, updates)
        
        return {
            'success': True,
            'confidence': metrics['confidence'],
            'segmentationComplete': True,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'metrics': metrics
        }

    def re_segment(self, patient_id):
        """Re-run segmentation for existing patient"""
        patient = firebase_service.get_patient_by_id(patient_id)
        if not patient:
            return None
        
        new_metrics = self._simulate_segmentation()
        return firebase_service.update_patient(patient_id, {'metrics': new_metrics})

    def _simulate_segmentation(self):
        """Simulate segmentation metrics"""
        return {
            'confidence': round(0.8 + np.random.random() * 0.15, 2),
            'dice_score': round(0.75 + np.random.random() * 0.15, 2),
            'iou_score': round(0.7 + np.random.random() * 0.15, 2)
        }

    def preprocess(self, image):
        img_min, img_max = np.min(image), np.max(image)
        if img_max - img_min == 0:
            return np.zeros_like(image)
        return (image - img_min) / (img_max - img_min)

    def predict(self, image):
        """Dummy prediction"""
        mask = np.zeros_like(image)
        h, w = mask.shape
        rr, cc = np.ogrid[:h, :w]
        radius = min(h, w) // 100
        mask[(rr - h//2)**2 + (cc - w//2)**2 <= radius**2] = 1
        
        metrics = self._simulate_segmentation()
        return mask, metrics

segmentation_service = SegmentationService()
