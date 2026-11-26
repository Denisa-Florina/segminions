import React from 'react';

/**
 * Shows the model's confidence as a percentage, or a clear warning when the result
 * was produced by the simulation fallback instead of the AI model.
 */
function ConfidenceValue({ confidence, simulated, className = '' }) {
  if (simulated) {
    return (
      <span
        className="px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-600/20 text-yellow-400"
        title="Modelul AI nu a fost disponibil: masca este un placeholder, nu o predicție."
      >
        Simulat – nu e rezultat AI
      </span>
    );
  }
  return <span className={className}>{((confidence || 0) * 100).toFixed(1)}%</span>;
}

export default ConfidenceValue;
