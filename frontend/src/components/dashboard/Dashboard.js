import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import patientService from '../../services/patientService';
import Sidebar from './Sidebar';
import DashboardView from './DashboardView';
import PatientsView from '../patients/PatientsView';
import PatientProfile from '../patients/PatientProfile';
import SettingsView from '../settings/SettingsView';
import AddPatientModal from '../patients/AddPatientModal';

function Dashboard() {
  const { doctor } = useAuth();
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeView, setActiveView] = useState('dashboard');
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [showAddPatient, setShowAddPatient] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    if (doctor?.id) {
      loadPatients();
    }
  }, [doctor]);

  const loadPatients = async () => {
    setLoading(true);
    try {
      const data = await patientService.getPatients();
      setPatients(data);
    } catch (err) {
      console.error('Error loading patients:', err);
    } finally {
      setLoading(false);
    }
  };
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
            onUpdate={loadPatients}
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
