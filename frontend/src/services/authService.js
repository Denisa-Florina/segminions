import api, { TOKEN_KEY } from './api';

const DOCTOR_KEY = 'doctor';

function saveSession({ doctor, token }) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(DOCTOR_KEY, JSON.stringify(doctor));
  return doctor;
}

export const authService = {
  async login(email, password) {
    const response = await api.post('/auth/login', { email, password });
    return saveSession(response.data);
  },

  /** Creates an account; the API signs the new doctor in straight away. */
  async register(details) {
    const response = await api.post('/auth/register', details);
    return saveSession(response.data);
  },

  async logout() {
    try {
      await api.post('/auth/logout');
    } finally {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(DOCTOR_KEY);
    }
  },

  async getCurrentDoctor() {
    // Without a token the stored doctor is useless: every API call would return 401.
    const token = localStorage.getItem(TOKEN_KEY);
    const doctor = localStorage.getItem(DOCTOR_KEY);
    if (!token || !doctor) {
      localStorage.removeItem(DOCTOR_KEY);
      return null;
    }
    return JSON.parse(doctor);
  }
};

export default authService;
