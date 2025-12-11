import api from './api';

export const patientService = {
  async getPatients(doctorId) {
    const response = await api.get(`/patients?doctor_id=${doctorId}`);
    return response.data.patients;
  },

  async getPatient(patientId) {
    const response = await api.get(`/patients/${patientId}`);
    return response.data.patient;
  },

  async createPatient(patientData, dicomFile) {
    const doctor = JSON.parse(localStorage.getItem('doctor'));
    if (!doctor) throw new Error("Doctor not found in localStorage");

    const formData = new FormData();
    formData.append('name', patientData.name);
    formData.append('age', patientData.age);
    formData.append('doctor_id', doctor.id);
    formData.append('dicom_file', dicomFile);

    const response = await api.post('/patients', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    
    return response.data.patient;
  },

  async updatePatient(patientId, updates) {
    const response = await api.put(`/patients/${patientId}`, updates);
    return response.data.patient;
  },

  async deletePatient(patientId) {
    await api.delete(`/patients/${patientId}`);
  },

  async uploadDicom(patientId, dicomFile) {
    const formData = new FormData();
    formData.append('dicom_file', dicomFile);

    const response = await api.post(`/patients/${patientId}/upload-dicom`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    
    return response.data.result;
  },

  async reSegmentPatient(patientId) {
    const response = await api.post(`/patients/${patientId}/re-segment`);
    return response.data.patient;
  }
};

export default patientService;