import { cn } from '../utils/cn';

export function EmptyState({
  action,
  compact = false,
  description,
  title,
}) {
  return (
    <div
      className={cn(
        'rounded-3xl border border-dashed border-slate-300 bg-white/70 text-center shadow-sm backdrop-blur dark:border-slate-700 dark:bg-slate-900/60',
        compact ? 'p-5' : 'p-8 md:p-10',
      )}
    >
      <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
