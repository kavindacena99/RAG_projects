import { Navigate } from 'react-router-dom';

import { AuthLayout } from '../components/AuthLayout';
import { SignupForm } from '../components/SignupForm';
import { useAuth } from '../hooks/useAuth';

export function SignupPage() {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate replace to="/chat" />;
  }

  return (
    <AuthLayout
      description="Create an account to access saved AI conversations, session history, and the streaming chat interface."
      eyebrow="Conversational RAG"
      title="Create your account"
    >
      <SignupForm />
    </AuthLayout>
  );
}
