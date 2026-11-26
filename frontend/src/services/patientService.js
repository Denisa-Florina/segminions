import api from './api';

// Segmentation runs in the background, so requests return quickly; only moving whole
// scans (uploading a DICOM series, loading a volume into the viewer) takes longer.
const LARGE_TRANSFER_TIMEOUT_MS = 2 * 60 * 1000;

function dicomFormData(dicomFiles, fields = {}) {
  const formData = new FormData();
  Object.entries(fields).forEach(([key, value]) => formData.append(key, value));
  (dicomFiles || []).forEach(file => formData.append('dicom_file', file));
  return formData;
}

function filenameFromHeaders(headers, fallback) {
  const match = headers['content-disposition']?.match(/filename="?([^";]+)"?/);
  return match ? match[1] : fallback;
}

/** Downloads `path` and hands it to the browser as a file to save. */
async function saveFile(path, fallbackName) {
  const response = await api.get(path, { responseType: 'blob' });
  const url = window.URL.createObjectURL(response.data);
  const link = document.createElement('a');
  link.href = url;
  link.download = filenameFromHeaders(response.headers, fallbackName);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export const patientService = {
  async getPatients() {
    const response = await api.get('/patients');
    return response.data.patients;
  },

  async getPatient(patientId) {
    const response = await api.get(`/patients/${patientId}`);
    return response.data.patient;
  },

  async createPatient(patientData, dicomFiles) {
    const formData = dicomFormData(dicomFiles, { name: patientData.name, age: patientData.age });
    const response = await api.post('/patients/', formData, { timeout: LARGE_TRANSFER_TIMEOUT_MS });
    return response.data.patient;
  },

  async updatePatient(patientId, updates) {
    const response = await api.put(`/patients/${patientId}`, updates);
    return response.data.patient;
  },

  async deletePatient(patientId) {
    await api.delete(`/patients/${patientId}`);
  },

  async uploadDicom(patientId, dicomFiles) {
    const response = await api.post(
      `/patients/${patientId}/upload-dicom`,
      dicomFormData(dicomFiles),
      { timeout: LARGE_TRANSFER_TIMEOUT_MS }
    );
    return response.data.result;
  },

  async reSegmentPatient(patientId) {
    const response = await api.post(`/patients/${patientId}/re-segment`);
    return response.data.patient;
  },

  // ===== Downloads =====

  downloadScan(patientId) {
    return saveFile(`/patients/${patientId}/download/scan`, `scan_${patientId}.nii.gz`);
  },

  downloadMask(patientId) {
    return saveFile(`/patients/${patientId}/download/mask`, `segmentation_${patientId}.nii.gz`);
  },

  downloadBoth(patientId) {
    return saveFile(`/patients/${patientId}/download/both`, `results_${patientId}.zip`);
  },

  // ===== Viewer =====

  /** Raw `.nii.gz` bytes of the scan or the mask (`kind` is "scan" or "mask"). */
  async getVolume(patientId, kind, signal) {
    const response = await api.get(`/patients/${patientId}/download/${kind}`, {
      responseType: 'arraybuffer',
      timeout: LARGE_TRANSFER_TIMEOUT_MS,
      signal,
    });
    return response.data;
  },
};

export default patientService;
