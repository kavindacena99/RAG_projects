import { useState } from 'react';

import { Button } from '../../../shared/components/Button';
import { TextArea } from '../../../shared/components/TextArea';

export function ChatInput({ disabled, errorMessage, isSending, onSend }) {
  const [message, setMessage] = useState('');

  async function submitCurrentMessage() {
    const nextMessage = message.trim();
    if (!nextMessage || disabled || isSending) {
      return;
    }

    setMessage('');
    await onSend(nextMessage);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    await submitCurrentMessage();
  }

  return (
    <div className="shrink-0 border-t border-slate-200 bg-white/90 px-4 py-4 backdrop-blur dark:border-slate-800 dark:bg-slate-950/85 md:px-6">
      <form className="mx-auto max-w-4xl" onSubmit={handleSubmit}>
        <TextArea
          disabled={disabled || isSending}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              void submitCurrentMessage();
            }
          }}
          placeholder={
            disabled
              ? 'Create or select a chat session to start.'
              : 'Ask a question about your knowledge base...'
          }
          rows={3}
          value={message}
        />

        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs leading-5 text-slate-400 dark:text-slate-500">
            Press Enter to send. Shift + Enter adds a new line.
          </p>
          <Button
            className="w-full sm:w-auto sm:min-w-[110px]"
            disabled={disabled || isSending || !message.trim()}
            isLoading={isSending}
            type="submit"
          >
            Send
          </Button>
        </div>

        {errorMessage ? (
          <p className="mt-3 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-500/25 dark:bg-rose-500/10 dark:text-rose-200">
            {errorMessage}
          </p>
        ) : null}
      </form>
    </div>
  );
}
