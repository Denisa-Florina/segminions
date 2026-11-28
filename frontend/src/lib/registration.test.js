import { utf8Length, validateRegistration } from './registration';

const valid = {
  name: 'Dr. Ana Pop', email: 'ana@example.com', password: 'long enough', confirmPassword: 'long enough',
};

describe('validateRegistration', () => {
  it('accepts a complete form', () => {
    expect(validateRegistration(valid)).toBeNull();
  });

  it('reports the first problem', () => {
    expect(validateRegistration({ ...valid, name: '  ' })).toBe('Name is required');
    expect(validateRegistration({ ...valid, email: '' })).toBe('Email is required');
    expect(validateRegistration({ ...valid, password: 'short', confirmPassword: 'short' }))
      .toMatch(/at least 8/);
    expect(validateRegistration({ ...valid, confirmPassword: 'different' }))
      .toBe('Passwords do not match');
  });

  it('measures the bcrypt limit in bytes, not characters', () => {
    const password = 'ă'.repeat(37); // 37 characters, 74 bytes in UTF-8
    expect(validateRegistration({ ...valid, password, confirmPassword: password }))
      .toBe('Password is too long');
  });
});

describe('utf8Length', () => {
  it('counts bytes like UTF-8', () => {
    expect(utf8Length('abc')).toBe(3);
    expect(utf8Length('ă')).toBe(2);
    expect(utf8Length('€')).toBe(3);
    expect(utf8Length('😀')).toBe(4);
  });
});
