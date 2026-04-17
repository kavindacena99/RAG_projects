import { useEffect, useRef } from 'react';

import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorState } from '../../../shared/components/ErrorState';
import { Spinner } from '../../../shared/components/Spinner';
import { AssistantMessage } from './AssistantMessage';
import { StreamingAssistantBubble } from './StreamingAssistantBubble';
import { UserMessage } from './UserMessage';

export function MessageList({ errorMessage, isLoading, messages, onOpenSources }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  if (isLoading && messages.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-4 md:px-6">
        <Spinner label="Loading messages" />
      </div>
    );
  }

  if (errorMessage && messages.length === 0) {
    return (
      <div className="px-4 py-6 md:px-6">
        <ErrorState
          description={errorMessage}
          title="Unable to load this conversation"
        />
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="px-4 py-6 md:px-6">
        <EmptyState
          description="Ask a question to begin the conversation. Responses will stream in as they are generated."
          title="This conversation is empty"
        />
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-6">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-5 md:gap-6">
        {messages.map((message) => {
          if (message.role === 'user') {
            return <UserMessage key={message.id} message={message} />;
          }

          if (message.isStreaming) {
            return (
              <StreamingAssistantBubble
                key={message.id}
                message={message}
                onShowSources={onOpenSources}
              />
            );
          }

          return (
            <AssistantMessage
              key={message.id}
              message={message}
              onShowSources={onOpenSources}
            />
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
