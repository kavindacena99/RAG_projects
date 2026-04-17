import { useQuery } from '@tanstack/react-query';

import { getMessages } from '../api/chatApi';
import { mapChatMessageFromApi } from '../utils/messageMappers';

export const messagesQueryKey = (sessionId) => ['messages', sessionId];

export function useMessagesQuery(sessionId) {
  return useQuery({
    enabled: Boolean(sessionId),
    queryKey: sessionId ? messagesQueryKey(sessionId) : ['messages', 'idle'],
    queryFn: async () => {
      const messages = await getMessages(sessionId);
      return messages.map(mapChatMessageFromApi);
    },
  });
}
