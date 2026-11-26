import { formatDate, isThisMonth } from './format';
import { initials } from '../components/common/Avatar';

describe('formatDate', () => {
  it('formats an ISO date without shifting it by the time zone', () => {
    expect(formatDate('2026-11-01')).toBe('Nov 1, 2026');
  });

  it('returns unknown values unchanged and empty ones as a dash', () => {
    expect(formatDate('yesterday')).toBe('yesterday');
    expect(formatDate('')).toBe('—');
  });
});

describe('isThisMonth', () => {
  const now = new Date(2026, 10, 26); // Nov 26, 2026
  it('compares year and month', () => {
    expect(isThisMonth('2026-11-01', now)).toBe(true);
    expect(isThisMonth('2026-10-31', now)).toBe(false);
    expect(isThisMonth('2025-11-26', now)).toBe(false);
    expect(isThisMonth(undefined, now)).toBe(false);
  });
});

describe('initials', () => {
  it('uses the first and last name', () => {
    expect(initials('Ana Maria Popescu')).toBe('AP');
    expect(initials('ion')).toBe('I');
    expect(initials('  ')).toBe('?');
  });
});
