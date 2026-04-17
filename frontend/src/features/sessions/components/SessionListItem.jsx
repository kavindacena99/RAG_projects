import { Button } from '../../../shared/components/Button';
import { cn } from '../../../shared/utils/cn';
import { formatSessionTimestamp } from '../../../shared/utils/date';

export function SessionListItem({ isActive, onDelete, onSelect, session }) {
  const label = session.title?.trim() || 'Untitled conversation';

  return (
    <li
      className={cn(
        'group flex items-center gap-2 rounded-2xl border px-2 py-2 transition',
        isActive
          ? 'border-sky-200 bg-sky-50/90'
          : 'border-transparent bg-white/70 hover:border-slate-200 hover:bg-white',
      )}
    >
      <button
        className="min-w-0 flex-1 text-left"
        onClick={() => onSelect(session.id)}
        type="button"
      >
        <p className="truncate text-sm font-medium text-slate-800">{label}</p>
        <p className="mt-1 text-xs text-slate-500">{formatSessionTimestamp(session.updated_at)}</p>
      </button>

      <Button
        className="opacity-100 transition lg:opacity-0 lg:group-hover:opacity-100"
        onClick={() => onDelete(session.id)}
        size="sm"
        type="button"
        variant="ghost"
      >
        Delete
      </Button>
    </li>
  );
}
