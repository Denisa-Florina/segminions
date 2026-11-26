import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import patientService from '../../services/patientService';
import Sidebar from './Sidebar';
import DashboardView from './DashboardView';
import PatientsView from '../patients/PatientsView';
import PatientProfile from '../patients/PatientProfile';
import SettingsView from '../settings/SettingsView';
import AddPatientModal from '../patients/AddPatientModal';

const LIST_POLL_INTERVAL_MS = 5000;

function Dashboard() {
  const { doctor } = useAuth();
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeView, setActiveView] = useState('dashboard');
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddPatient, setShowAddPatient] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  // `silent` refreshes the list without the loading spinner (used while polling).
  const loadPatients = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    try {
      const data = await patientService.getPatients();
      setPatients(data);
    } catch (err) {
      console.error('Error loading patients:', err);
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (doctor?.id) {
      loadPatients();
    }
  }, [doctor, loadPatients]);

  // Segmentation runs in the background: refresh the list until no scan is processing.
  // (The patient profile polls its own patient.)
  const anyProcessing = patients.some(p => p.status === 'processing');
  useEffect(() => {
    if (!anyProcessing || activeView === 'patient') return undefined;
    const timer = setInterval(() => loadPatients({ silent: true }), LIST_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [anyProcessing, activeView, loadPatients]);
  // Average only over real AI results: unsegmented and simulated patients have no
  // meaningful confidence.
  const scored = patients.filter(p => p.status === 'completed' && !p.simulated);
  const stats = {
    totalPatients: patients.length,
    completed: patients.filter(p => p.status === 'completed').length,
    avgConfidence: scored.length > 0
      ? (scored.reduce((sum, p) => sum + (p.confidence || 0), 0) / scored.length * 100).toFixed(1)
      : 0,
    thisMonth: patients.filter(p => {
      const pDate = new Date(p.date);
      const now = new Date();
      return pDate.getMonth() === now.getMonth() && pDate.getFullYear() === now.getFullYear();
    }).length
  };

  const filteredPatients = patients.filter(p => 
    p.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleViewPatient = (patient) => {
    setSelectedPatient(patient);
    setActiveView('patient');
  };

  return (
    <div className="min-h-screen bg-gray-900 flex">
      <Sidebar 
        activeView={activeView} 
        setActiveView={setActiveView}
        setShowSettings={setShowSettings}
      />

      <main className="flex-1 overflow-auto">
        {activeView === 'dashboard' && (
          <DashboardView 
            stats={stats} 
            patients={patients} 
            onViewPatient={handleViewPatient}
            loading={loading}
          />
        )}

        {activeView === 'patients' && (
          <PatientsView
            patients={filteredPatients}
            searchTerm={searchTerm}
            setSearchTerm={setSearchTerm}
            onViewPatient={handleViewPatient}
            onAddPatient={() => setShowAddPatient(true)}
            loading={loading}
          />
        )}

        {activeView === 'patient' && selectedPatient && (
          <PatientProfile
            patient={selectedPatient}
            onBack={() => setActiveView('patients')}
            onUpdate={() => loadPatients({ silent: true })}
          />
        )}

        {showSettings && (
          <SettingsView 
            doctor={doctor} 
            onClose={() => setShowSettings(false)} 
          />
        )}
      </main>

      {showAddPatient && (
        <AddPatientModal
          onClose={() => setShowAddPatient(false)}
          onSuccess={() => {
            setShowAddPatient(false);
            loadPatients();
          }}
        />
      )}
    </div>
  );
}

export default Dashboard;
