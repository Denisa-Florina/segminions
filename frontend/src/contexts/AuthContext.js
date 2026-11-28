import React, { createContext, useContext, useState, useEffect } from 'react';
import { authService } from '../services/authService';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [doctor, setDoctor] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const currentDoctor = await authService.getCurrentDoctor();
      setDoctor(currentDoctor);
    } catch (err) {
      setDoctor(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      setError(null);
      const loggedInDoctor = await authService.login(email, password);
      setDoctor(loggedInDoctor);
      return { success: true };
    } catch (err) {
      setError(err.message || 'Login failed');
      return { success: false, error: err.message };
    }
  };

  const register = async (details) => {
    try {
      setError(null);
      setDoctor(await authService.register(details));
      return { success: true };
    } catch (err) {
      setError(err.message || 'Registration failed');
      return { success: false, error: err.message };
    }
  };

  const logout = async () => {
    // The local session ends even when the server cannot be reached: otherwise a
    // network error would leave the doctor "logged in" with no way out.
    try {
      await authService.logout();
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setDoctor(null);
    }
  };

  const value = {
    doctor,
    loading,
    error,
    login,
    register,
    logout,
    isAuthenticated: !!doctor
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div role="status" className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" aria-label="Loading" />
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};