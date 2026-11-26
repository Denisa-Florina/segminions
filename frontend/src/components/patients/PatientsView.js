import React from 'react';
import { Link, useOutletContext, useSearchParams } from 'react-router-dom';
import { Plus, Search, Users } from 'lucide-react';
import Avatar from '../common/Avatar';
import LoadError from '../common/LoadError';
import { PatientCardSkeleton } from '../common/Skeleton';
import ConfidenceValue from './ConfidenceValue';
import StatusBadge from './StatusBadge';
import { formatDate } from '../../lib/format';

function PatientCard({ patient }) {
  return (
    <Link
      to={`/patients/${patient.id}`}
      className="block bg-gray-800 border border-gray-700 rounded-xl p-6 hover:border-blue-500 hover:bg-gray-800/80 transition"
    >
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-3 min-w-0">
          <Avatar name={patient.name} />
          <div className="min-w-0">
            <h3 className="font-semibold text-white truncate">{patient.name}</h3>
            <p className="text-sm text-gray-400">{patient.age} years</p>
          </div>
        </div>
        <StatusBadge status={patient.status} className="shrink-0" />
      </div>

      <dl className="space-y-2 text-sm">
        <div className="flex justify-between">
          <dt className="text-gray-400">Date</dt>
          <dd className="text-white">{formatDate(patient.date)}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-gray-400">Confidence</dt>
          <dd>
            <ConfidenceValue
              confidence={patient.confidence}
              simulated={patient.simulated}
              status={patient.status}
              className="font-medium"
            />
          </dd>
        </div>
        {patient.dicomFile && (
          <div className="flex justify-between gap-4">
            <dt className="text-gray-400">File</dt>
            <dd className="text-gray-300 text-xs truncate max-w-[150px]" title={patient.dicomFile}>
              {patient.dicomFile}
            </dd>
          </div>
        )}
      </dl>
    </Link>
  );
}

function PatientsView() {
  const { patients, loading, loadError, reloadPatients, openAddPatient } = useOutletContext();
  // The search lives in the URL (?q=...), so it survives a refresh and the back button.
  const [searchParams, setSearchParams] = useSearchParams();
  const searchTerm = searchParams.get('q') || '';

  const setSearchTerm = (value) => {
    setSearchParams(value ? { q: value } : {}, { replace: true });
  };

  const filtered = patients.filter(p =>
    p.name.toLowerCase().includes(searchTerm.trim().toLowerCase())
  );

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-3xl font-bold text-white mb-2">Patients</h2>
          <p className="text-gray-400">Manage your patients and their scans</p>
        </div>
        <button
          type="button"
          onClick={openAddPatient}
          className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition font-medium"
        >
          <Plus className="w-5 h-5" aria-hidden="true" />
          Add patient
        </button>
      </div>

      {loadError && <LoadError message={loadError} onRetry={() => reloadPatients()} />}

      <div className="relative mb-6">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" aria-hidden="true" />
        <input
          type="search"
          aria-label="Search patients by name"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder="Search patients…"
          className="w-full bg-gray-800 text-white pl-12 pr-4 py-3 rounded-lg border border-gray-700 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/40 focus:outline-none"
        />
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[0, 1, 2, 3, 4, 5].map(i => <PatientCardSkeleton key={i} />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12">
          <Users className="w-16 h-16 text-gray-600 mx-auto mb-4" aria-hidden="true" />
          {searchTerm ? (
            <p className="text-gray-400 text-lg">No patients match “{searchTerm}”</p>
          ) : (
            <>
              <p className="text-gray-400 text-lg">No patients yet</p>
              <button
                type="button"
                onClick={openAddPatient}
                className="mt-4 px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition"
              >
                Add your first patient
              </button>
            </>
          )}
        </div>
      ) : (
        <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map(patient => (
            <li key={patient.id}>
              <PatientCard patient={patient} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default PatientsView;
