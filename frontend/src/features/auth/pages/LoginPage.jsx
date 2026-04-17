import { Navigate } from 'react-router-dom';

import { AuthLayout } from '../components/AuthLayout';
import { LoginForm } from '../components/LoginForm';
import { useAuth } from '../hooks/useAuth';

export function LoginPage() {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate replace to="/chat" />;
  }

  return (
    <AuthLayout
      description="A focused frontend for conversational RAG with persistent sessions, streaming answers, and room to grow."
      eyebrow="Conversational RAG"
      title="Sign in to your chat workspace"
    >
      <LoginForm />
    </AuthLayout>
  );
}
