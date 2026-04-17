import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../../features/auth/hooks/useAuth';

export function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate replace to="/login" state={{ from: location }} />;
  }

  return <>{children}</>;
}
