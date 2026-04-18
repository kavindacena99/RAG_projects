import { AppProviders } from './providers/AppProviders';
import { AppRouter } from './router/AppRouter';

export function App() {
  return (
    <div className="h-full bg-transparent text-slate-900 transition-colors dark:text-slate-100">
      <AppProviders>
        <AppRouter />
      </AppProviders>
    </div>
  );
}
