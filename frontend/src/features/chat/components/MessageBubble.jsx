import { cn } from '../../../shared/utils/cn';
import { formatMessageTimestamp } from '../../../shared/utils/date';

export function MessageBubble({ actions, label, message }) {
  const timestamp = formatMessageTimestamp(message.created_at);

  return (
    <article
      className={cn(
        'flex w-full flex-col gap-2',
        message.role === 'user' ? 'items-end' : 'items-start',
      )}
    >
      <div
        className={cn(
          'w-full max-w-full rounded-[1.5rem] px-4 py-3 shadow-sm sm:max-w-[90%] xl:max-w-3xl',
          message.role === 'user'
            ? 'bg-slate-900 text-white'
            : message.error
              ? 'border border-rose-200 bg-rose-50 text-rose-900'
              : 'border border-slate-200 bg-white text-slate-900',
        )}
      >
        <div className="mb-2 flex items-center justify-between gap-3 text-xs">
          <span
            className={cn(
              'font-semibold uppercase tracking-[0.18em]',
              message.role === 'user' ? 'text-slate-300' : 'text-slate-400',
            )}
          >
            {label}
          </span>
          {timestamp ? (
            <time
              className={cn(
                message.role === 'user' ? 'text-slate-300' : 'text-slate-400',
              )}
              dateTime={message.created_at}
            >
              {timestamp}
            </time>
          ) : null}
        </div>

        <p className="whitespace-pre-wrap break-words text-sm leading-7">
          {message.content || (message.isStreaming ? 'Thinking...' : 'No response content.')}
        </p>
      </div>

      <div className="flex w-full max-w-full flex-col gap-2 px-1 sm:max-w-[90%] sm:flex-row sm:items-center sm:justify-between xl:max-w-3xl">
        <div className="text-xs text-slate-400">
          {message.isStreaming ? 'Streaming response...' : message.error ?? ''}
        </div>
        {actions}
      </div>
    </article>
  );
}
