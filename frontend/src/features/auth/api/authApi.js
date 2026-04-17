import { apiClient } from '../../../shared/lib/apiClient';

export function login(payload) {
  return apiClient.post('/auth/login', payload, { skipAuth: true });
}

export function register(payload) {
  return apiClient.post('/auth/register', payload, { skipAuth: true });
}
