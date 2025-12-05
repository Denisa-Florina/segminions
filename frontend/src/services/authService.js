import api from './api';

export const authService = {
  async login(email, password) {
    const response = await api.post('/auth/login', { email, password });
    
    if (response.data.token) {
      localStorage.setItem('authToken', response.data.token);
    }
    
    return response.data.doctor;
  },

  async logout() {
    await api.post('/auth/logout');
    localStorage.removeItem('authToken');
  },

  async getCurrentDoctor() {
    const token = localStorage.getItem('authToken');
    if (!token) return null;
    
    const response = await api.get('/auth/me');
    return response.data.doctor;
  }
};

export default authService;