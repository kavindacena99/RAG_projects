import { useQueryClient } from '@tanstack/react-query';
import {
  useEffect,
  useEffectEvent,
  useState,
} from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { configureApiClient } from '../../../shared/lib/apiClient';
import { AuthContext } from './AuthContext';
import { clearStoredAuth, loadStoredAuth, saveStoredAuth } from '../utils/authStorage';

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => loadStoredAuth());
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const handleUnauthorized = useEffectEvent(() => {
    clearStoredAuth();
    setSession(null);
    queryClient.clear();

    if (!location.pathname.startsWith('/login')) {
      navigate('/login', {
        replace: true,
        state: { reason: 'expired' },
      });
    }
  });

  useEffect(() => {
    configureApiClient({
      getAccessToken: () => session?.access_token ?? null,
      onUnauthorized: () => handleUnauthorized(),
    });

    return () => {
      configureApiClient({
        getAccessToken: () => null,
        onUnauthorized: () => undefined,
      });
    };
  }, [session?.access_token]);

  function login(auth) {
    saveStoredAuth(auth);
    setSession(auth);
  }

  function logout(options = {}) {
    clearStoredAuth();
    setSession(null);
    queryClient.clear();

    if (options.redirectToLogin !== false) {
      navigate('/login', { replace: true });
    }
  }

  const value = {
    accessToken: session?.access_token ?? null,
    isAuthenticated: Boolean(session?.access_token),
    login,
    logout,
    user: session?.user ?? null,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
