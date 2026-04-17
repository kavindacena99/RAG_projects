import { AppProviders } from './providers/AppProviders';
import { AppRouter } from './router/AppRouter';

export function App() {
  return (
    <div className="min-h-screen text-slate-900">
      <AppProviders>
        <AppRouter />
      </AppProviders>
    </div>
  );
}
