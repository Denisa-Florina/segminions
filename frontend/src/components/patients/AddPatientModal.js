import React, { useEffect, useState } from 'react';
import { X, Upload } from 'lucide-react';
import patientService from '../../services/patientService';

const INPUT_CLASS =
  'w-full bg-gray-700 text-white px-4 py-2 rounded-lg border border-gray-600 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/40 focus:outline-none';

function AddPatientModal({ onClose, onSuccess }) {
  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [dicomFiles, setDicomFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Escape closes the dialog, except while the patient is being saved.
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape' && !loading) onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [loading, onClose]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !age) {
      setError('Name and age are required');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const patient = await patientService.createPatient(
        { name: name.trim(), age: parseInt(age, 10) },
        dicomFiles
      );
      onSuccess(patient);
    } catch (err) {
      setError(err.message || 'Could not add the patient');
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50"
      onMouseDown={(e) => { if (e.target === e.currentTarget && !loading) onClose(); }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-patient-title"
        className="bg-gray-800 rounded-2xl p-6 w-full max-w-md border border-gray-700 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-6">
          <h3 id="add-patient-title" className="text-2xl font-bold text-white">New patient</h3>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            aria-label="Close"
            className="text-gray-400 hover:text-white rounded-lg p-1"
          >
            <X className="w-6 h-6" aria-hidden="true" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="patient-name" className="block text-sm font-medium text-gray-300 mb-2">
              Name <span className="text-red-400" aria-hidden="true">*</span>
            </label>
            <input
              id="patient-name"
              type="text"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={INPUT_CLASS}
              placeholder="Full name"
              required
            />
          </div>

          <div>
            <label htmlFor="patient-age" className="block text-sm font-medium text-gray-300 mb-2">
              Age <span className="text-red-400" aria-hidden="true">*</span>
            </label>
            <input
              id="patient-age"
              type="number"
              value={age}
              onChange={(e) => setAge(e.target.value)}
              className={INPUT_CLASS}
              placeholder="Age in years"
              min="1"
              max="150"
              required
            />
          </div>

          <div>
            <span className="block text-sm font-medium text-gray-300 mb-2">
              DICOM files <span className="text-gray-500">(optional)</span>
            </span>
            <label className="block border-2 border-dashed border-gray-600 rounded-lg p-6 text-center hover:border-blue-500 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/40 transition cursor-pointer">
              <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" aria-hidden="true" />
              <p className="text-sm text-gray-300">
                {dicomFiles.length
                  ? `${dicomFiles.length} file${dicomFiles.length === 1 ? '' : 's'} selected`
                  : 'Click to choose the slices of a series'}
              </p>
              <input
                type="file"
                accept=".dcm"
                multiple
                onChange={(e) => setDicomFiles(Array.from(e.target.files))}
                className="sr-only"
              />
            </label>
          </div>

          {error && (
            <div role="alert" className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-3 rounded-lg text-sm">
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !name.trim() || !age}
              className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Adding…' : 'Add patient'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default AddPatientModal;
