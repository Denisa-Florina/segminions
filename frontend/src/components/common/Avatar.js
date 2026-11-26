import React from 'react';

// Background colours that keep white text readable (WCAG AA) on every one of them.
const COLORS = [
  'bg-blue-600', 'bg-emerald-600', 'bg-violet-600', 'bg-rose-600',
  'bg-amber-600', 'bg-cyan-600', 'bg-indigo-600', 'bg-teal-600',
];

const SIZES = {
  sm: 'w-10 h-10 text-sm',
  md: 'w-12 h-12 text-base',
  lg: 'w-24 h-24 text-3xl',
};

export function initials(name = '') {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '?';
  const first = words[0][0];
  const last = words.length > 1 ? words[words.length - 1][0] : '';
  return (first + last).toUpperCase();
}

// The same name always gets the same colour, so a patient is recognisable across pages.
function colorFor(name = '') {
  let hash = 0;
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) | 0;
  return COLORS[Math.abs(hash) % COLORS.length];
}

function Avatar({ name, size = 'md' }) {
  return (
    <div
      aria-hidden="true"
      className={`${SIZES[size]} ${colorFor(name)} shrink-0 rounded-full flex items-center justify-center font-semibold text-white`}
    >
      {initials(name)}
    </div>
  );
}

export default Avatar;
