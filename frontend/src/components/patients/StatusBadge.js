import React from 'react';

const STATUSES = {
  pending: { label: 'Fără scanare', className: 'bg-gray-600/20 text-gray-300' },
  processing: { label: 'În procesare', className: 'bg-yellow-600/20 text-yellow-400' },
  completed: { label: 'Completat', className: 'bg-green-600/20 text-green-400' },
  failed: { label: 'Eșuat', className: 'bg-red-600/20 text-red-400' },
};

function StatusBadge({ status, className = '' }) {
  const { label, className: colors } = STATUSES[status] || STATUSES.pending;
  return (
    <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${colors} ${className}`}>
      {label}
    </span>
  );
}

export default StatusBadge;
