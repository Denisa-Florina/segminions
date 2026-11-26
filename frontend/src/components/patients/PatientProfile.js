import React, { useState, useEffect, useRef } from 'react';
import { User, Upload, CheckCircle, ArrowLeft, Download, AlertTriangle, RefreshCw } from 'lucide-react';
import patientService from '../../services/patientService';
import ConfidenceValue from './ConfidenceValue';
import StatusBadge from './StatusBadge';

const POLL_INTERVAL_MS = 3000;

function PatientProfile({ patient: initialPatient, onBack, onUpdate }) {
  const [patient, setPatient] = useState(initialPatient);
  const [uploading, setUploading] = useState(false);
  const [requestError, setRequestError] = useState('');
  const [downloading, setDownloading] = useState(false);
  const isProcessing = patient.status === 'processing';

  // Keep the latest callback without restarting the polling timer on every render.
  const onUpdateRef = useRef(onUpdate);
  useEffect(() => { onUpdateRef.current = onUpdate; }, [onUpdate]);

  // The list only has a summary: load the full patient (metrics, error message).
  useEffect(() => {
    setPatient(initialPatient);
    patientService.getPatient(initialPatient.id)
      .then(setPatient)
      .catch(err => console.error('Error loading patient:', err));
  }, [initialPatient]);

  // Segmentation runs in the background: poll until it completes or fails.
  useEffect(() => {
    if (!isProcessing) return undefined;
    const timer = setInterval(async () => {
      try {
        const latest = await patientService.getPatient(patient.id);
        setPatient(latest);
        if (latest.status !== 'processing') onUpdateRef.current();
      } catch (err) {
        console.error('Error refreshing patient:', err);
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [isProcessing, patient.id]);

  const startProcessing = () => {
    setPatient(p => ({ ...p, status: 'processing', segmentationError: null }));
    onUpdateRef.current();
  };

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    e.target.value = '';   // allow selecting the same files again
    if (files.length === 0) return;

    setUploading(true);
    setRequestError('');
    try {
      await patientService.uploadDicom(patient.id, files);
      startProcessing();
    } catch (err) {
      setRequestError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleResegment = async () => {
    setRequestError('');
    try {
      await patientService.reSegmentPatient(patient.id);
      startProcessing();
    } catch (err) {
      setRequestError(err.message);
    }
  };

  const handleDownloadScan = async () => {
    setDownloading(true);
    try {
      await patientService.downloadScan(patient.id);
    } catch (error) {
      alert('Eroare la descărcarea scan-ului: ' + error.message);
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadMask = async () => {
    setDownloading(true);
    try {
      await patientService.downloadMask(patient.id);
    } catch (error) {
      alert('Eroare la descărcarea segmentării: ' + error.message);
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadBoth = async () => {
    setDownloading(true);
    try {
      await patientService.downloadBoth(patient.id);
    } catch (error) {
      alert('Eroare la descărcarea fișierelor: ' + error.message);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="p-8">
      <button
        onClick={onBack}
        className="flex items-center gap-2  bg-gray-900 text-gray-400 hover:text-white mb-6 transition"
      >
        <ArrowLeft className="w-5 h-5" />
        Înapoi la pacienți
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Patient Info */}
        <div className="lg:col-span-1">
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
            <div className="text-center mb-6">
              <div className="w-24 h-24 bg-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <User className="w-12 h-12 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-1">{patient.name}</h2>
              <p className="text-gray-400">{patient.age} ani</p>
            </div>

            <div className="space-y-3 border-t border-gray-700 pt-6">
              <div className="flex justify-between">
                <span className="text-gray-400">ID Pacient:</span>
                <span className="text-white font-medium">#{patient.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Data scanării:</span>
                <span className="text-white font-medium">{patient.date}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Status:</span>
                <StatusBadge status={patient.status} />
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Confidence:</span>
                <ConfidenceValue
                  confidence={patient.confidence}
                  simulated={patient.simulated}
                  className="text-white font-medium"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Upload & Results */}
        <div className="lg:col-span-2 space-y-6">
          {/* Upload Section */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
            <h3 className="text-xl font-bold text-white mb-4">
              Încarcă fișiere DICOM pentru predicție
            </h3>

            <label className="block">
              <div className="border-2 border-dashed border-gray-600 rounded-xl p-8 text-center hover:border-blue-500 transition cursor-pointer">
                <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-white font-medium mb-2">
                  {uploading ? 'Se încarcă scanarea...'
                    : isProcessing ? 'Segmentare în curs...'
                    : 'Click pentru a încărca fișier DICOM'}
                </p>
                <p className="text-sm text-gray-400">Formatul acceptat: .dcm</p>
                <input
                  type="file"
                  accept=".dcm" multiple
                  onChange={handleFileUpload}
                  disabled={uploading || isProcessing}
                  className="hidden"
                />
              </div>
            </label>

            {(uploading || isProcessing) && (
              <div className="mt-4 bg-blue-600/20 border border-blue-500 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <div className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                  <span className="text-blue-400">
                    {uploading
                      ? 'Se încarcă și se verifică scanarea...'
                      : 'Segmentarea rulează în fundal și poate dura câteva minute. Poți părăsi pagina.'}
                  </span>
                </div>
              </div>
            )}

            {requestError && (
              <div className="mt-4 bg-red-600/20 border border-red-500 rounded-lg p-4 text-sm text-red-300">
                {requestError}
              </div>
            )}

            {patient.status === 'failed' && (
              <div className="mt-4 bg-red-600/20 border border-red-500 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  <span className="text-red-400 font-medium">Segmentarea a eșuat</span>
                </div>
                <p className="text-sm text-gray-300 mb-3">
                  {patient.segmentationError || 'A apărut o eroare la procesare.'}
                </p>
                <button
                  onClick={handleResegment}
                  className="flex items-center gap-2 px-3 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm transition"
                >
                  <RefreshCw className="w-4 h-4" />
                  Reîncearcă segmentarea
                </button>
              </div>
            )}

            {patient.status === 'completed' && (
              <div className="mt-4 bg-green-600/20 border border-green-500 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                  <CheckCircle className="w-5 h-5 text-green-400" />
                  <span className="text-green-400 font-medium">Segmentare completă!</span>
                </div>
                <p className="text-sm text-gray-300">
                  Confidence:{' '}
                  <ConfidenceValue confidence={patient.confidence} simulated={patient.simulated} />
                </p>
              </div>
            )}
          </div>

          {/* Results Section */}
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-6">
            <h3 className="text-xl font-bold text-white mb-4">Rezultate Segmentare</h3>

            {/* <div className="bg-gray-700/50 rounded-lg p-4 mb-4">
              <div className="aspect-video bg-gray-900 rounded-lg flex items-center justify-center">
                <FileText className="w-16 h-16 text-gray-600" />
              </div>
              <p className="text-sm text-gray-400 mt-2 text-center">
                Vizualizare rezultate segmentare
              </p>
            </div> */}

            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="bg-gray-700/50 rounded-lg p-4">
                <p className="text-sm text-gray-400 mb-1">Confidence Score</p>
                <p className="text-2xl font-bold text-white">
                  <ConfidenceValue confidence={patient.confidence} simulated={patient.simulated} />
                </p>
              </div>
              <div className="bg-gray-700/50 rounded-lg p-4">
                <p className="text-sm text-gray-400 mb-1">Volum segmentat</p>
                <p className="text-2xl font-bold text-white">
                  {patient.metrics?.volume_mm3 != null
                    ? `${patient.metrics.volume_mm3.toLocaleString('ro-RO')} mm³`
                    : '—'}
                </p>
              </div>
              {/* <div className="bg-gray-700/50 rounded-lg p-4">
                <p className="text-sm text-gray-400 mb-1">Fișier</p>
                <p className="text-sm font-medium text-white truncate">
                  {patient.filename || 'N/A'}
                </p>
                {patient.file_size && (
                  <p className="text-xs text-gray-400 mt-1">
                    Size: {(patient.file_size / (1024 * 1024)).toFixed(2)} MB
                  </p>
                )}
              </div> */}
            </div>

            {/* Download Buttons */}
            {patient.status === 'completed' && (
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-gray-400 mb-3">Descarcă Rezultate:</h4>

                <button
                  onClick={handleDownloadScan}
                  disabled={downloading}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-lg transition font-medium"
                >
                  <Download className="w-5 h-5" />
                  {downloading ? 'Se descarcă...' : 'Descarcă CT Scan (.nii.gz)'}
                </button>

                <button
                  onClick={handleDownloadMask}
                  disabled={downloading}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white rounded-lg transition font-medium"
                >
                  <Download className="w-5 h-5" />
                  {downloading ? 'Se descarcă...' : 'Descarcă Segmentare (.nii.gz)'}
                </button>

                <button
                  onClick={handleDownloadBoth}
                  disabled={downloading}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 text-black rounded-lg transition font-medium"
                >
                  <Download className="w-5 h-5" />
                  {downloading ? 'Se descarcă...' : 'Descarcă Ambele (ZIP)'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default PatientProfile;