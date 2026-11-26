import React from 'react';
import { useAuth } from '../../contexts/AuthContext';
import Avatar from '../common/Avatar';

const FIELDS = [
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email' },
  { key: 'specialization', label: 'Specialization' },
  { key: 'hospital', label: 'Hospital' },
];

/**
 * The logged-in doctor's profile. Read-only: the API has no endpoint for editing a
 * doctor yet, so the page does not offer controls that would do nothing.
 */
function AccountView() {
  const { doctor } = useAuth();

  return (
    <div className="p-8">
      <div className="mb-8">
        <h2 className="text-3xl font-bold text-white mb-2">Account</h2>
        <p className="text-gray-400">Your profile as stored in MedSeg AI</p>
      </div>

      <section className="max-w-2xl bg-gray-800 border border-gray-700 rounded-xl p-6">
        <div className="flex items-center gap-4 mb-6">
          <Avatar name={doctor.name} size="md" />
          <div>
            <p className="text-lg font-semibold text-white">{doctor.name}</p>
            <p className="text-sm text-gray-400">{doctor.specialization}</p>
          </div>
        </div>

        <dl className="divide-y divide-gray-700 border-t border-gray-700">
          {FIELDS.map(({ key, label }) => (
            <div key={key} className="flex justify-between gap-4 py-3 text-sm">
              <dt className="text-gray-400">{label}</dt>
              <dd className="text-white">{doctor[key] || '—'}</dd>
            </div>
          ))}
        </dl>

        <p className="mt-6 text-xs text-gray-500">
          To change these details, contact your administrator.
        </p>
      </section>
    </div>
  );
}

export default AccountView;
