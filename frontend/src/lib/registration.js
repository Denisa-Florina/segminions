// Mirrors the API's rules (backend/app/schemas/doctor.py), so most mistakes are caught
// before a request. The API still validates everything.
export const MIN_PASSWORD_LENGTH = 8;
// bcrypt uses only the first 72 bytes of a password (bytes, not characters).
const MAX_PASSWORD_BYTES = 72;

/** Bytes the text takes in UTF-8, the encoding the password is hashed in. */
export function utf8Length(text) {
  let bytes = 0;
  for (const char of text) {
    const code = char.codePointAt(0);
    bytes += code < 0x80 ? 1 : code < 0x800 ? 2 : code < 0x10000 ? 3 : 4;
  }
  return bytes;
}

/** Returns the first problem with the registration form, or null when it is valid. */
export function validateRegistration({ name, email, password, confirmPassword }) {
  if (!name.trim()) return 'Name is required';
  if (!email.trim()) return 'Email is required';
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters`;
  }
  if (utf8Length(password) > MAX_PASSWORD_BYTES) {
    return 'Password is too long';
  }
  if (password !== confirmPassword) return 'Passwords do not match';
  return null;
}
