import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { Button } from '../../../shared/components/Button';
import { Input } from '../../../shared/components/Input';
import { getApiErrorMessage } from '../../../shared/types/api';
import { login as loginRequest } from '../api/authApi';
import { useAuth } from '../hooks/useAuth';

export function LoginForm() {
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [formError, setFormError] = useState(null);
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const loginMutation = useMutation({
    mutationFn: loginRequest,
    onSuccess: (response) => {
      auth.login(response);
      const redirectTo = location.state?.from?.pathname ?? '/chat';
      navigate(redirectTo, { replace: true });
    },
    onError: (error) => {
      setFormError(getApiErrorMessage(error, 'Unable to sign in right now.'));
    },
  });

  function handleSubmit(event) {
    event.preventDefault();
    setFormError(null);

    if (!identifier.trim() || !password.trim()) {
      setFormError('Enter both your username or email and your password.');
      return;
    }

    loginMutation.mutate({
      identifier: identifier.trim(),
      password,
    });
  }

  return (
    <div className="w-full rounded-[2rem] border border-white/70 bg-white/90 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur dark:border-slate-800 dark:bg-slate-950/80 dark:shadow-[0_24px_60px_rgba(2,6,23,0.45)] md:p-8">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Sign in</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
          Continue your saved conversations and start new retrieval sessions.
        </p>
      </div>

      <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700 dark:text-slate-300" htmlFor="login-identifier">
            Username or email
          </label>
          <Input
            autoComplete="username"
            id="login-identifier"
            onChange={(event) => setIdentifier(event.target.value)}
            placeholder="jane or jane@example.com"
            value={identifier}
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-700 dark:text-slate-300" htmlFor="login-password">
            Password
          </label>
          <Input
            autoComplete="current-password"
            id="login-password"
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Enter your password"
            type="password"
            value={password}
          />
        </div>

        {formError ? (
          <p className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-200">
            {formError}
          </p>
        ) : null}

        <Button className="w-full" isLoading={loginMutation.isPending} type="submit">
          Sign in
        </Button>
      </form>

      <p className="mt-6 text-sm text-slate-500 dark:text-slate-400">
        New here?{' '}
        <Link className="font-medium text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300" to="/signup">
          Create an account
        </Link>
      </p>
    </div>
  );
}
