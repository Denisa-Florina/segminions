import numpy as np
import time
from datetime import datetime
from backend.data.database import db
import os

class SegmentationService:
    def __init__(self):
        self.model_loaded = True

    def process_dicom(self, dicom_file, patient_data, doctor_id):
        """Process initial DICOM file when creating a patient"""
        time.sleep(0.5)
        
        filename = self._save_dicom_file(dicom_file)
        
        metrics = self._simulate_segmentation()
        
        patient = {
            'name': patient_data['name'],
            'age': patient_data['age'],
            'dicom_file': filename,
            'doctor_id': doctor_id,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'segmented': True,
            'metrics': metrics
        }
        
        return db.add_patient(patient)

    def process_uploaded_dicom(self, dicom_file, patient_id):
        """Process a newly uploaded DICOM file for existing patient"""
        time.sleep(1.5)
        
        filename = self._save_dicom_file(dicom_file)
        
        metrics = self._simulate_segmentation()
        
        updates = {
            'dicom_file': filename,
            'metrics': metrics,
            'segmented': True,
            'date': datetime.now().strftime('%Y-%m-%d')
        }
        
        db.update_patient(patient_id, updates)
        
        return {
            'success': True,
            'confidence': metrics['confidence'],
            'segmentationComplete': True,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'metrics': metrics
        }

    def re_segment(self, patient_id):
        """Re-run segmentation on existing patient"""
        time.sleep(0.5)
        
        patient = db.get_patient_by_id(patient_id)
        if not patient:
            return None
        
        new_metrics = self._simulate_segmentation()
        
        return db.update_patient(patient_id, {'metrics': new_metrics})

    def _save_dicom_file(self, dicom_file):
        """Save uploaded DICOM file to uploads folder"""
        if hasattr(dicom_file, 'filename'):
            filename = f"{int(time.time())}_{dicom_file.filename}"
            filepath = os.path.join('uploads', filename)
            dicom_file.save(filepath)
            return filename
        return 'mock.dcm'

    def _simulate_segmentation(self):
        """Simulate segmentation metrics"""
        return {
            'confidence': round(0.80 + np.random.random() * 0.15, 2),
            'dice_score': round(0.75 + np.random.random() * 0.15, 2),
            'iou_score': round(0.70 + np.random.random() * 0.15, 2)
        }

    def preprocess(self, image):
        img_min, img_max = np.min(image), np.max(image)
        if img_max - img_min == 0:
            return np.zeros_like(image)
        return (image - img_min) / (img_max - img_min)

    def predict(self, image):
        mask = np.zeros_like(image)
        h, w = mask.shape
        rr, cc = np.ogrid[:h, :w]
        radius = min(h, w) // 100
        circle = (rr - h//2)**2 + (cc - w//2)**2 <= radius**2
        mask[circle] = 1
        
        metrics = self._simulate_segmentation()
        
        return mask, metrics

segmentation_service = SegmentationService()