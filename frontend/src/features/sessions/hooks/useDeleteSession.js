import { useMutation, useQueryClient } from '@tanstack/react-query';

import { deleteSession } from '../api/sessionsApi';
import { SESSIONS_QUERY_KEY } from './useSessionsQuery';

export function useDeleteSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteSession,
    onSuccess: (_, sessionId) => {
      queryClient.setQueryData(SESSIONS_QUERY_KEY, (currentSessions = []) =>
        currentSessions.filter((session) => session.id !== sessionId),
      );
    },
  });
}
