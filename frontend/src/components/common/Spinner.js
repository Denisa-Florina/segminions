import React from 'react';

function Spinner({ className = 'w-5 h-5 border-2 border-blue-400' }) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className={`${className} border-t-transparent rounded-full animate-spin`}
    />
  );
}

export default Spinner;
