import React, { useState } from 'react';
import { User, Lock, Activity } from 'lucide-react';
import { useAuth } from '../../../src/contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

function LoginScreen() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setError('');
    setLoading(true);

    const result = await login(email, password);
    
    if (result.success) {
      navigate('/patients'); 
    } else {
      setError(result.error || 'Email sau parolă incorectă');
    }
    
    setLoading(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleLogin();
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <div className="login-header-icon">
            <Activity className="w-12 h-12 text-blue-600" />
          </div>
          <h1>MedSeg AI</h1>
          <p>Segmentare arteră etmoidală</p>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyPress={handleKeyPress}
                className="login-input"
                placeholder="doctor@hospital.ro"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Parolă</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyPress={handleKeyPress}
                className="login-input"
                placeholder="••••••••"
              />
            </div>
          </div>

          {error && <div className="login-error">{error}</div>}

          <button
            onClick={handleLogin}
            disabled={loading || !email || !password}
            className="login-button"
          >
            {loading ? 'Se conectează...' : 'Autentificare'}
          </button>
        </div>

        <div className="login-demo">
          <p>Demo credentials:</p>
          <p>📧 dr.popescu@hospital.ro</p>
          <p>🔑 password123</p>
        </div>
      </div>
    </div>
  );
}

export default LoginScreen;
