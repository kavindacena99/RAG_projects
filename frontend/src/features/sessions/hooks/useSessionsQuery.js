import { useQuery } from '@tanstack/react-query';

import { listSessions } from '../api/sessionsApi';

export const SESSIONS_QUERY_KEY = ['sessions'];

export function useSessionsQuery() {
  return useQuery({
    queryKey: SESSIONS_QUERY_KEY,
    queryFn: listSessions,
  });
}
