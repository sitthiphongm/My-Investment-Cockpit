import axios from 'axios';
import toast from 'react-hot-toast';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor — attach credentials (cookies are sent via withCredentials)
apiClient.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor — handle auth errors, user states, and display toasts
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (axios.isAxiosError(error) && error.response) {
      const status = error.response.status;
      const detail = error.response.data?.detail || 'An unexpected error occurred';
      const errorCode = error.response.data?.error_code;

      // Handle specific user state error codes from backend
      if (errorCode === 'PENDING_APPROVAL') {
        toast.error('Your account is pending approval.');
        window.location.href = '/login?status=pending';
        return Promise.reject(error);
      }

      if (errorCode === 'ACCOUNT_BLOCKED') {
        toast.error('Your account has been blocked.');
        window.location.href = '/login?error=account_blocked';
        return Promise.reject(error);
      }

      switch (status) {
        case 401:
          // Redirect to login on authentication failure
          // Only redirect if not already on the login page or making the /me check
          if (!window.location.pathname.startsWith('/login')) {
            window.location.href = '/login';
          }
          break;
        case 403:
          if (errorCode === 'ACCESS_DENIED') {
            toast.error('Access denied. Admin privileges required.');
          } else {
            toast.error(detail || 'Access denied');
          }
          break;
        case 422:
          // Validation errors — show first error message
          if (error.response.data?.detail) {
            if (Array.isArray(error.response.data.detail)) {
              const firstError = error.response.data.detail[0];
              toast.error(firstError?.msg || 'Validation error');
            } else {
              toast.error(error.response.data.detail);
            }
          }
          break;
        default:
          toast.error(detail);
          break;
      }
    } else {
      toast.error('Network error. Please check your connection.');
    }

    return Promise.reject(error);
  }
);
