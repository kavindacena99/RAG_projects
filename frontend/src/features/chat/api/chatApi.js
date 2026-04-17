import { apiClient } from '../../../shared/lib/apiClient';

export function getMessages(sessionId) {
  return apiClient.get(`/chat/messages/${sessionId}`);
}

export function sendMessageStream(payload) {
  return apiClient.stream('/chat/send-message', {
    body: payload,
    method: 'POST',
  });
}
