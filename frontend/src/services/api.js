import axios from 'axios';

// Base API URL - change for production
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';


const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, 
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json'
  }
});


api.interceptors.request.use(
  (config) => {
    // Putem adauga un token
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);


api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response;
      
      if (status === 401) {
        window.location.href = '/login';
      } else if (status === 404) {
        console.error('Resource not found:', data.error);
      } else if (status === 500) {
        console.error('Server error:', data.error);
      }
      
      return Promise.reject(new Error(data.error || 'An error occurred'));
    } else if (error.request) {
      return Promise.reject(new Error('No response from server'));
    } else {
      return Promise.reject(error);
    }
  }
);

export default api;