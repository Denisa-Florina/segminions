import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginScreen from './components/auth/LoginScreen';
import AppLayout from './components/layout/AppLayout';
import DashboardView from './components/dashboard/DashboardView';
import PatientsView from './components/patients/PatientsView';
import PatientProfile from './components/patients/PatientProfile';
import AccountView from './components/account/AccountView';

// Remembers the page that was asked for, so login can return to it (e.g. a shared
// link to /patients/123 opened while logged out).
function PrivateRoute({ children }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  return isAuthenticated ? children : <Navigate to="/login" replace state={{ from: location }} />;
}

// A logged-in doctor who opens /login goes on to where they were heading.
function PublicOnlyRoute({ children }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  const destination = location.state?.from?.pathname || '/dashboard';
  return isAuthenticated ? <Navigate to={destination} replace /> : children;
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<PublicOnlyRoute><LoginScreen /></PublicOnlyRoute>} />
          <Route element={<PrivateRoute><AppLayout /></PrivateRoute>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardView />} />
            <Route path="patients" element={<PatientsView />} />
            <Route path="patients/:patientId" element={<PatientProfile />} />
            <Route path="account" element={<AccountView />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
