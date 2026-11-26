import React from 'react';

// Display thresholds only: they colour the number to draw attention to weak results,
// they are not a clinical cut-off.
const HIGH = 0.85;
const MEDIUM = 0.6;

export function confidenceColor(confidence) {
  if (confidence >= HIGH) return 'text-green-400';
  if (confidence >= MEDIUM) return 'text-yellow-400';
  return 'text-red-400';
}

/**
 * Shows the model's confidence as a percentage, or a clear warning when the result
 * was produced by the simulation fallback instead of the AI model.
 */
function ConfidenceValue({ confidence, simulated, status, className = '' }) {
  if (simulated) {
    return (
      <span
        className="px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-600/20 text-yellow-400"
        title="The AI model was unavailable: this mask is a placeholder, not a prediction."
      >
        Simulated – not an AI result
      </span>
    );
  }
  // Without a finished segmentation there is no confidence to show (not 0%).
  if (status !== 'completed' || confidence == null) {
    return <span className={`text-gray-500 ${className}`}>—</span>;
  }
  return (
    <span className={`${confidenceColor(confidence)} ${className}`}>
      {(confidence * 100).toFixed(1)}%
    </span>
  );
}

export default ConfidenceValue;
