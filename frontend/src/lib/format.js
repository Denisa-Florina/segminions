/**
 * Formats a "YYYY-MM-DD" date from the API as e.g. "Nov 26, 2026".
 * The parts are read by hand: `new Date("2026-11-26")` is UTC midnight, which shows as
 * the previous day in time zones west of UTC.
 */
export function formatDate(isoDate) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate || '');
  if (!match) return isoDate || '—';
  const [, year, month, day] = match.map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  });
}

/** True when a "YYYY-MM-DD" date falls in the current calendar month. */
export function isThisMonth(isoDate, now = new Date()) {
  const match = /^(\d{4})-(\d{2})/.exec(isoDate || '');
  return !!match && Number(match[1]) === now.getFullYear() && Number(match[2]) === now.getMonth() + 1;
}
