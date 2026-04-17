import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { Button } from '../../../shared/components/Button';
import { Input } from '../../../shared/components/Input';
import { getApiErrorMessage } from '../../../shared/types/api';
import { register as registerRequest } from '../api/authApi';
import { useAuth } from '../hooks/useAuth';

export function SignupForm() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [formError, setFormError] = useState(null);
  const auth = useAuth();
  const navigate = useNavigate();

  const registerMutation = useMutation({
    mutationFn: registerRequest,
    onSuccess: (response) => {
      auth.login(response);
      navigate('/chat', { replace: true });
    },
    onError: (error) => {
      setFormError(getApiErrorMessage(error, 'Unable to create your account.'));
    },
  });

  function handleSubmit(event) {
    event.preventDefault();
    setFormError(null);

    if (!username.trim() || !email.trim() || !password) {
      setFormError('Complete all required fields to continue.');
      return;
    }

    if (password.length < 8) {
      setFormError('Use a password with at least 8 characters.');
      return;
    }

    if (password !== confirmPassword) {
      setFormError('Your password confirmation does not match.');
      return;
    }

    registerMutation.mutate({
      email: email.trim(),
      password,
      username: username.trim(),
    });
  }

  return (
    <div className="w-full rounded-[2rem] border border-white/70 bg-white/90 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur md:p-8">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900">Create account</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          Set up your workspace access and jump straight into the chat app.
        </p>
      </div>

      <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700" htmlFor="signup-username">
            Username
          </label>
          <Input
            autoComplete="username"
            id="signup-username"
            onChange={(event) => setUsername(event.target.value)}
            placeholder="janedoe"
            value={username}
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700" htmlFor="signup-email">
            Email
          </label>
          <Input
            autoComplete="email"
            id="signup-email"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="jane@example.com"
            type="email"
            value={email}
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700" htmlFor="signup-password">
            Password
          </label>
          <Input
            autoComplete="new-password"
            id="signup-password"
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Minimum 8 characters"
            type="password"
            value={password}
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700" htmlFor="signup-confirm-password">
            Confirm password
          </label>
          <Input
            autoComplete="new-password"
            id="signup-confirm-password"
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder="Re-enter your password"
            type="password"
            value={confirmPassword}
          />
        </div>

        {formError ? (
          <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {formError}
          </p>
        ) : null}

        <Button className="w-full" isLoading={registerMutation.isPending} type="submit">
          Create account
        </Button>
      </form>

      <p className="mt-6 text-sm text-slate-500">
        Already have an account?{' '}
        <Link className="font-medium text-sky-600 hover:text-sky-700" to="/login">
          Sign in
        </Link>
      </p>
    </div>
  );
}
