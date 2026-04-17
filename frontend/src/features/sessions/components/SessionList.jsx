import { EmptyState } from '../../../shared/components/EmptyState';
import { Spinner } from '../../../shared/components/Spinner';
import { SessionListItem } from './SessionListItem';

export function SessionList({
  activeSessionId,
  isLoading,
  onDeleteSession,
  onSelectSession,
  sessions,
}) {
  if (isLoading && sessions.length === 0) {
    return (
      <div className="rounded-3xl border border-dashed border-slate-300 bg-white/70 p-5">
        <Spinner label="Loading conversations" />
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <EmptyState
        compact
        description="Start your first chat session and it will appear here."
        title="No conversations yet"
      />
    );
  }

  return (
    <ul className="space-y-2">
      {sessions.map((session) => (
        <SessionListItem
          isActive={session.id === activeSessionId}
          key={session.id}
          onDelete={onDeleteSession}
          onSelect={onSelectSession}
          session={session}
        />
      ))}
    </ul>
  );
}
