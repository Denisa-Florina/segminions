import React, { useState, useEffect, useRef } from 'react';
import { Link, useOutletContext, useParams } from 'react-router-dom';
import { Upload, CheckCircle, ArrowLeft, Download, AlertTriangle, RefreshCw, SearchX } from 'lucide-react';
import patientService from '../../services/patientService';
import Avatar from '../common/Avatar';
import Spinner from '../common/Spinner';
import { Skeleton } from '../common/Skeleton';
import ConfidenceValue from './ConfidenceValue';
import SegmentationViewer from './SegmentationViewer';
import StatusBadge from './StatusBadge';
import { formatDate } from '../../lib/format';

const POLL_INTERVAL_MS = 3000;

const DOWNLOADS = [
  { kind: 'scan', label: 'CT scan (.nii.gz)', run: patientService.downloadScan, color: 'bg-blue-600 hover:bg-blue-700' },
  { kind: 'mask', label: 'Segmentation (.nii.gz)', run: patientService.downloadMask, color: 'bg-green-600 hover:bg-green-700' },
  { kind: 'both', label: 'Both (ZIP)', run: patientService.downloadBoth, color: 'bg-violet-600 hover:bg-violet-700' },
];

function ErrorBox({ children }) {
  return (
    <div role="alert" className="mt-4 bg-red-600/20 border border-red-500 rounded-lg p-4 text-sm text-red-300">
      {children}
    </div>
  );
}

function InfoRow({ label, children }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-gray-400">{label}</dt>
      <dd className="text-white font-medium text-right">{children}</dd>
    </div>
  );
}

function PatientProfile() {
  const { patientId } = useParams();
  const { patients, reloadPatients } = useOutletContext();
  // Start from the list's summary (if loaded) so the page renders immediately; the
  // full patient (metrics, error message) is fetched below.
  const summary = patients.find(p => p.id === patientId) || null;
  const [patient, setPatient] = useState(summary);
  const [notFound, setNotFound] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [requestError, setRequestError] = useState('');
  const [downloading, setDownloading] = useState(null); // kind being downloaded
  const isProcessing = patient?.status === 'processing';
  // Read through a ref so the effect below refetches only when the URL changes, not
  // every time the list refreshes and `summary` becomes a new object.
  const summaryRef = useRef(summary);
  summaryRef.current = summary;

  useEffect(() => {
    let cancelled = false;
    setPatient(summaryRef.current);
    setNotFound(false);
    setRequestError('');
    patientService.getPatient(patientId)
      .then(full => { if (!cancelled) setPatient(full); })
      .catch(err => {
        if (cancelled) return;
        // The API answers 404 both for a missing patient and for another doctor's.
        if (err.status === 404) setNotFound(true);
        else setRequestError(err.message);
      });
    return () => { cancelled = true; };
  }, [patientId]);

  // Segmentation runs in the background: poll until it completes or fails.
  useEffect(() => {
    if (!isProcessing) return undefined;
    const timer = setInterval(async () => {
      try {
        const latest = await patientService.getPatient(patientId);
        setPatient(latest);
        if (latest.status !== 'processing') reloadPatients({ silent: true });
      } catch (err) {
        console.error('Error refreshing patient:', err);
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [isProcessing, patientId, reloadPatients]);

  const startProcessing = () => {
    setPatient(p => ({ ...p, status: 'processing', segmentationError: null }));
    reloadPatients({ silent: true });
  };

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    e.target.value = ''; // allow selecting the same files again
    if (files.length === 0) return;

    setUploading(true);
    setRequestError('');
    try {
      await patientService.uploadDicom(patientId, files);
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
      await patientService.reSegmentPatient(patientId);
      startProcessing();
    } catch (err) {
      setRequestError(err.message);
    }
  };

  const handleDownload = async ({ kind, run }) => {
    setDownloading(kind);
    setRequestError('');
    try {
      await run(patientId);
    } catch (err) {
      setRequestError(`Download failed: ${err.message}`);
    } finally {
      setDownloading(null);
    }
  };

  const backLink = (
    <Link to="/patients" className="inline-flex items-center gap-2 text-gray-400 hover:text-white mb-6 transition">
      <ArrowLeft className="w-5 h-5" aria-hidden="true" />
      Back to patients
    </Link>
  );

  if (notFound) {
    return (
      <div className="p-8">
        {backLink}
        <div className="text-center py-16">
          <SearchX className="w-16 h-16 text-gray-600 mx-auto mb-4" aria-hidden="true" />
          <p className="text-xl text-white font-semibold mb-2">Patient not found</p>
          <p className="text-gray-400">It may have been deleted, or the link is wrong.</p>
        </div>
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="p-8">
        {backLink}
        {requestError ? <ErrorBox>{requestError}</ErrorBox> : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Skeleton className="h-80 rounded-xl" />
            <Skeleton className="h-80 rounded-xl lg:col-span-2" />
          </div>
        )}
      </div>
    );
  }

  const metrics = patient.metrics || {};
  const busy = uploading || isProcessing;

  return (
    <div className="p-8">
      {backLink}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Patient info */}
        <section className="bg-gray-800 border border-gray-700 rounded-xl p-6">
          <div className="flex flex-col items-center text-center mb-6">
            <div className="mb-4"><Avatar name={patient.name} size="lg" /></div>
            <h2 className="text-2xl font-bold text-white mb-1">{patient.name}</h2>
            <p className="text-gray-400">{patient.age} years</p>
          </div>

          <dl className="space-y-3 border-t border-gray-700 pt-6 text-sm">
            <InfoRow label="Patient ID"><span className="font-mono text-xs text-gray-300">{patient.id}</span></InfoRow>
            <InfoRow label="Scan date">{formatDate(patient.date)}</InfoRow>
            <InfoRow label="Status"><StatusBadge status={patient.status} /></InfoRow>
            <InfoRow label="Confidence">
              <ConfidenceValue confidence={patient.confidence} simulated={patient.simulated} status={patient.status} />
            </InfoRow>
            {patient.dicomFile && (
              <InfoRow label="File">
                <span className="block truncate max-w-[160px] text-gray-300" title={patient.dicomFile}>{patient.dicomFile}</span>
              </InfoRow>
            )}
          </dl>
        </section>

        <div className="lg:col-span-2 space-y-6">
          {/* Upload */}
          <section className="bg-gray-800 border border-gray-700 rounded-xl p-6">
            <h3 className="text-xl font-bold text-white mb-4">Upload a DICOM series</h3>

            {/* The input is visually hidden but still focusable, so the drop zone works
                from the keyboard (Tab, then Enter or Space). */}
            <label
              className={`block border-2 border-dashed rounded-xl p-8 text-center transition focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/40 ${
                busy ? 'border-gray-700 cursor-not-allowed opacity-60' : 'border-gray-600 hover:border-blue-500 cursor-pointer'
              }`}
            >
              <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" aria-hidden="true" />
              <p className="text-white font-medium mb-2">
                {uploading ? 'Uploading scan…'
                  : isProcessing ? 'Segmentation in progress…'
                  : patient.status === 'pending' ? 'Click to choose DICOM files'
                  : 'Click to upload a new scan'}
              </p>
              <p className="text-sm text-gray-400">Accepted format: .dcm (select all slices of the series)</p>
              <input
                type="file"
                accept=".dcm"
                multiple
                onChange={handleFileUpload}
                disabled={busy}
                className="sr-only"
              />
            </label>

            {busy && (
              <div role="status" className="mt-4 bg-blue-600/20 border border-blue-500 rounded-lg p-4 flex items-center gap-3">
                <Spinner />
                <span className="text-blue-300 text-sm">
                  {uploading
                    ? 'Uploading and checking the scan…'
                    : 'Segmentation is running in the background and can take a few minutes. You can leave this page.'}
                </span>
              </div>
            )}

            {requestError && <ErrorBox>{requestError}</ErrorBox>}

            {patient.status === 'failed' && (
              <div role="alert" className="mt-4 bg-red-600/20 border border-red-500 rounded-lg p-4">
                <div className="flex items-center gap-3 mb-2">
                  <AlertTriangle className="w-5 h-5 text-red-400" aria-hidden="true" />
                  <span className="text-red-400 font-medium">Segmentation failed</span>
                </div>
                <p className="text-sm text-gray-300 mb-3">
                  {patient.segmentationError || 'An error occurred while processing the scan.'}
                </p>
                <button
                  type="button"
                  onClick={handleResegment}
                  className="flex items-center gap-2 px-3 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm transition"
                >
                  <RefreshCw className="w-4 h-4" aria-hidden="true" />
                  Retry segmentation
                </button>
              </div>
            )}
          </section>

          {/* Results */}
          {patient.status === 'completed' && (
            <section className="bg-gray-800 border border-gray-700 rounded-xl p-6">
              <div className="flex items-center gap-3 mb-4">
                <CheckCircle className="w-6 h-6 text-green-400" aria-hidden="true" />
                <h3 className="text-xl font-bold text-white">Segmentation results</h3>
              </div>

              <SegmentationViewer patientId={patientId} />

              <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4 my-6">
                <div className="bg-gray-700/50 rounded-lg p-4">
                  <dt className="text-sm text-gray-400 mb-1">Confidence</dt>
                  <dd className="text-2xl font-bold">
                    <ConfidenceValue confidence={patient.confidence} simulated={patient.simulated} status={patient.status} />
                  </dd>
                </div>
                <div className="bg-gray-700/50 rounded-lg p-4">
                  <dt className="text-sm text-gray-400 mb-1">Segmented volume</dt>
                  <dd className="text-2xl font-bold text-white">
                    {metrics.volume_mm3 != null
                      ? `${metrics.volume_mm3.toLocaleString('en-US', { maximumFractionDigits: 1 })} mm³`
                      : '—'}
                  </dd>
                </div>
                <div className="bg-gray-700/50 rounded-lg p-4">
                  <dt className="text-sm text-gray-400 mb-1">Segmented voxels</dt>
                  <dd className="text-2xl font-bold text-white">
                    {metrics.voxel_count != null ? metrics.voxel_count.toLocaleString('en-US') : '—'}
                  </dd>
                </div>
              </dl>

              <h4 className="text-sm font-semibold text-gray-400 mb-3">Download results</h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {DOWNLOADS.map(download => (
                  <button
                    key={download.kind}
                    type="button"
                    onClick={() => handleDownload(download)}
                    disabled={downloading !== null}
                    className={`flex items-center justify-center gap-2 px-4 py-3 ${download.color} text-white rounded-lg transition font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed`}
                  >
                    {downloading === download.kind ? <Spinner className="w-4 h-4 border-2 border-white" /> : <Download className="w-4 h-4" aria-hidden="true" />}
                    {download.label}
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

export default PatientProfile;
