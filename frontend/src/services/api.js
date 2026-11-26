import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:5001/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
});

export const TOKEN_KEY = 'authToken';

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Binary requests (downloads, the viewer) receive their JSON error body as raw bytes.
async function errorMessage(data) {
  try {
    if (data instanceof Blob) data = JSON.parse(await data.text());
    else if (data instanceof ArrayBuffer) data = JSON.parse(new TextDecoder().decode(data));
  } catch {
    return null;
  }
  return data?.error || null;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // A request cancelled on purpose (e.g. the page was left) is not a server problem.
    if (axios.isCancel(error)) return Promise.reject(error);

    if (error.response) {
      const { status, data } = error.response;

      console.error('API Error:', {
        status,
        data,
        url: error.config?.url,
        method: error.config?.method
      });
      
      if (status === 401 && window.location.pathname !== '/login') {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem('doctor');
        window.location.href = '/login';
      }
      
      const apiError = new Error((await errorMessage(data)) || 'An error occurred');
      apiError.status = status;
      return Promise.reject(apiError);
    }
    return Promise.reject(new Error('No response from server'));
  }
);

export default api;