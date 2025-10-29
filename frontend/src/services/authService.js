import api from './api';

export const authService = {

  async login(email, password) {
    const response = await api.post('/auth/login', { email, password });
    return response.data.doctor;
  },


  async logout() {
    await api.post('/auth/logout');
  },

 
  async getCurrentDoctor() {
    const response = await api.get('/auth/me');
    return response.data.doctor;
  }
};

export default authService;