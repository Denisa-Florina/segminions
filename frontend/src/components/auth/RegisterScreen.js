import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import AuthLayout, { AUTH_INPUT_CLASS, FormError } from './AuthLayout';
import { MIN_PASSWORD_LENGTH, validateRegistration } from '../../lib/registration';

const EMPTY_FORM = {
  name: '', email: '', password: '', confirmPassword: '', specialization: '', hospital: '',
};

function Field({ id, label, optional, hint, ...inputProps }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-300 mb-2">
        {label}{' '}
        {optional
          ? <span className="text-gray-500">(optional)</span>
          : <span className="text-red-400" aria-hidden="true">*</span>}
      </label>
      <input
        id={id}
        name={id}
        className={AUTH_INPUT_CLASS}
        aria-describedby={hint ? `${id}-hint` : undefined}
        {...inputProps}
      />
      {hint && <p id={`${id}-hint`} className="mt-1 text-xs text-gray-500">{hint}</p>}
    </div>
  );
}

function RegisterScreen() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const destination = location.state?.from?.pathname || '/dashboard';
  const update = (e) => setForm(current => ({ ...current, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    const problem = validateRegistration(form);
    if (problem) {
      setError(problem);
      return;
    }

    setError('');
    setLoading(true);
    const { name, email, password, specialization, hospital } = form;
    const result = await register({ name, email, password, specialization, hospital });
    setLoading(false);

    if (result.success) {
      navigate(destination, { replace: true });
    } else {
      setError(result.error || 'Could not create the account');
    }
  };

  return (
    <AuthLayout
      subtitle="Create your doctor account"
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" state={location.state} className="text-blue-400 hover:text-blue-300 font-medium">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <Field id="name" label="Full name" value={form.name} onChange={update}
          autoComplete="name" placeholder="Dr. Ana Popescu" required />
        <Field id="email" label="Email" type="email" value={form.email} onChange={update}
          autoComplete="email" placeholder="doctor@hospital.ro" required />
        <Field id="password" label="Password" type="password" value={form.password} onChange={update}
          autoComplete="new-password" hint={`At least ${MIN_PASSWORD_LENGTH} characters`} required />
        <Field id="confirmPassword" label="Confirm password" type="password" value={form.confirmPassword}
          onChange={update} autoComplete="new-password" required />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field id="specialization" label="Specialization" optional value={form.specialization}
            onChange={update} placeholder="Radiology" />
          <Field id="hospital" label="Hospital" optional value={form.hospital}
            onChange={update} autoComplete="organization" />
        </div>

        {error && <FormError>{error}</FormError>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthLayout>
  );
}

export default RegisterScreen;
