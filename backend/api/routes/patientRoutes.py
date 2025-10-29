
from flask import Blueprint, request, jsonify
from backend.services.segmentationService import segmentation_service
from backend.data.database import db

patient_bp = Blueprint('patients', __name__, url_prefix='/api/patients')


@patient_bp.route('/', methods=['GET'])
def get_patients():
    doctor_id = request.args.get('doctor_id', type=int)
    
    if not doctor_id:
        return jsonify({'error': 'doctor_id is required'}), 400
    
    patients = db.get_patients_by_doctor(doctor_id)
    return jsonify({'patients': patients}), 200


@patient_bp.route('/<int:patient_id>', methods=['GET'])
def get_patient(patient_id):
    patient = db.get_patient_by_id(patient_id)
    
    if not patient:
        return jsonify({'error': 'Patient not found'}), 404
    
    return jsonify({'patient': patient}), 200


@patient_bp.route('/', methods=['POST'])
def create_patient():
    try:
        name = request.form.get('name')
        age = request.form.get('age', type=int)
        doctor_id = request.form.get('doctor_id', type=int)
        
        if 'dicom_file' not in request.files:
            return jsonify({'error': 'No DICOM file uploaded'}), 400
        
        dicom_file = request.files['dicom_file']
        
        if not all([name, age, doctor_id]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        patient_data = {'name': name, 'age': age}
        patient = segmentation_service.process_dicom(dicom_file, patient_data, doctor_id)
        
        return jsonify({
            'message': 'Patient created successfully',
            'patient': patient
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@patient_bp.route('/<int:patient_id>', methods=['PUT'])
def update_patient(patient_id):
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Only allow updating name and age
        allowed_fields = {'name', 'age'}
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        
        patient = db.update_patient(patient_id, updates)
        
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        return jsonify({
            'message': 'Patient updated successfully',
            'patient': patient
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@patient_bp.route('/<int:patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    """
    DELETE /api/patients/1
    Delete patient
    """
    try:
        patient = db.get_patient_by_id(patient_id)
        
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        db.delete_patient(patient_id)
        
        return jsonify({'message': 'Patient deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@patient_bp.route('/<int:patient_id>/re-segment', methods=['POST'])
def re_segment_patient(patient_id):
    """
    POST /api/patients/1/re-segment
    Re-run segmentation on patient
    """
    try:
        patient = segmentation_service.re_segment(patient_id)
        
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        return jsonify({
            'message': 'Re-segmentation completed',
            'patient': patient
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500