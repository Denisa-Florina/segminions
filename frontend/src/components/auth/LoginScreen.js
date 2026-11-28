import React, { useState } from 'react';
import { Mail, Lock } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import AuthLayout, { AUTH_INPUT_CLASS, FormError } from './AuthLayout';

function LoginScreen() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Return to the page that sent us here (see PrivateRoute), or the dashboard.
  const destination = location.state?.from?.pathname || '/dashboard';

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const result = await login(email, password);
    setLoading(false);

    if (result.success) {
      navigate(destination, { replace: true });
    } else {
      setError(result.error || 'Incorrect email or password');
    }
  };

  return (
    <AuthLayout
      subtitle="Ethmoidal artery segmentation from CT"
      footer={
        <>
          New to MedSeg AI?{' '}
          {/* Keep `from`, so registering also returns to the page that was asked for. */}
          <Link to="/register" state={location.state} className="text-blue-400 hover:text-blue-300 font-medium">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={handleLogin} className="space-y-6">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">Email</label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" aria-hidden="true" />
            <input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={`${AUTH_INPUT_CLASS} pl-10`}
              placeholder="doctor@hospital.ro"
              required
            />
          </div>
        </div>

        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">Password</label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" aria-hidden="true" />
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`${AUTH_INPUT_CLASS} pl-10`}
              placeholder="••••••••"
              required
            />
          </div>
        </div>

        {error && <FormError>{error}</FormError>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <div className="mt-6 p-4 bg-gray-700/50 rounded-lg text-sm text-gray-300 text-center space-y-1">
        <p className="font-semibold">Demo account</p>
        <p>dr.popescu@hospital.ro</p>
        <p>password123</p>
      </div>
    </AuthLayout>
  );
}

export default LoginScreen;
