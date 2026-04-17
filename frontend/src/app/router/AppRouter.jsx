import { Navigate, Route, Routes } from 'react-router-dom';

import { useAuth } from '../../features/auth/hooks/useAuth';
import { LoginPage } from '../../features/auth/pages/LoginPage';
import { SignupPage } from '../../features/auth/pages/SignupPage';
import { ChatPage } from '../../features/chat/pages/ChatPage';
import { ProtectedRoute } from './ProtectedRoute';

function HomeRedirect() {
  const { isAuthenticated } = useAuth();

  return <Navigate replace to={isAuthenticated ? '/chat' : '/login'} />;
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  );
}
