import api from './api';

export const authService = {

  async login(email, password) {
    const response = await api.post('/auth/login', { email, password });
    
    const { token, doctor } = response.data;

    if (token) {
      localStorage.setItem('authToken', token); 
    }
    
    return response.data.doctor;
  },


  async logout() {
    await api.post('/auth/logout');
  },

 
  async getCurrentDoctor() {
    const token = localStorage.getItem('authToken');
    if (!token) return null;
    
    const response = await api.get('/auth/me');
    return response.data.doctor;
  }
};

export default authService;