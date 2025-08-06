import axios from 'axios';
import { getAuthToken } from './auth-client';

// Create axios instance that automatically includes auth token
const api = axios.create();

// Add request interceptor to include auth token
api.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers['x-auth-token'] = token;
  }
  return config;
});

// Add response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token might be invalid, redirect to login
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default api;