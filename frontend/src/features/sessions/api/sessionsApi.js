import { apiClient } from '../../../shared/lib/apiClient';

export function listSessions() {
  return apiClient.get('/chat/sessions');
}

export function createSession() {
  return apiClient.post('/chat/start-session', {});
}

export function deleteSession(sessionId) {
  return apiClient.delete(`/chat/session/${sessionId}`);
}
