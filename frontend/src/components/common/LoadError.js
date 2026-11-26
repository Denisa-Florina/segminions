import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

function LoadError({ message, onRetry }) {
  return (
    <div role="alert" className="mb-6 flex items-center justify-between gap-4 bg-red-600/20 border border-red-500 rounded-lg p-4">
      <div className="flex items-center gap-3 text-red-300 text-sm">
        <AlertTriangle className="w-5 h-5 shrink-0" aria-hidden="true" />
        Could not load patients: {message}
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="flex items-center gap-2 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm"
      >
        <RefreshCw className="w-4 h-4" aria-hidden="true" />
        Retry
      </button>
    </div>
  );
}

export default LoadError;
