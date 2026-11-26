import React, { useState, useEffect, useCallback } from 'react';
import { Outlet, useMatch, useNavigate } from 'react-router-dom';
import patientService from '../../services/patientService';
import Sidebar from './Sidebar';
import AddPatientModal from '../patients/AddPatientModal';

const LIST_POLL_INTERVAL_MS = 5000;

/**
 * Shell for every logged-in page: sidebar, the routed page (<Outlet />) and the
 * "add patient" dialog. It owns the patient list, which pages read through
 * useOutletContext(), so moving between pages does not reload it.
 */
function AppLayout() {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [showAddPatient, setShowAddPatient] = useState(false);
  const onPatientPage = useMatch('/patients/:patientId');
  const navigate = useNavigate();
  // Stable identity, so the dialog's Escape listener is not re-registered every render.
  const closeAddPatient = useCallback(() => setShowAddPatient(false), []);

  // `silent` refreshes the list without the loading state (used while polling).
  const loadPatients = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    try {
      setPatients(await patientService.getPatients());
      setLoadError('');
    } catch (err) {
      setLoadError(err.message);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPatients();
  }, [loadPatients]);

  // Segmentation runs in the background: refresh the list until no scan is processing.
  // (The patient page polls its own patient.)
  const anyProcessing = patients.some(p => p.status === 'processing');
  useEffect(() => {
    if (!anyProcessing || onPatientPage) return undefined;
    const timer = setInterval(() => loadPatients({ silent: true }), LIST_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [anyProcessing, onPatientPage, loadPatients]);

  const context = {
    patients,
    loading,
    loadError,
    reloadPatients: loadPatients,
    openAddPatient: () => setShowAddPatient(true),
  };

  return (
    <div className="h-screen bg-gray-900 flex">
      <Sidebar />

      <main className="flex-1 overflow-auto scrollbar-dark">
        <Outlet context={context} />
      </main>

      {showAddPatient && (
        <AddPatientModal
          onClose={closeAddPatient}
          onSuccess={(patient) => {
            setShowAddPatient(false);
            loadPatients({ silent: true });
            navigate(`/patients/${patient.id}`);
          }}
        />
      )}
    </div>
  );
}

export default AppLayout;
