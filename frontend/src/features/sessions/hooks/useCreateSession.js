import { useMutation, useQueryClient } from '@tanstack/react-query';

import { createSession } from '../api/sessionsApi';
import { SESSIONS_QUERY_KEY } from './useSessionsQuery';

export function useCreateSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createSession,
    onSuccess: (session) => {
      queryClient.setQueryData(SESSIONS_QUERY_KEY, (currentSessions = []) => [
        session,
        ...currentSessions.filter((currentSession) => currentSession.id !== session.id),
      ]);
    },
  });
}
