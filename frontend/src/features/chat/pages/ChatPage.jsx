import { startTransition, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { Button } from '../../../shared/components/Button';
import { EmptyState } from '../../../shared/components/EmptyState';
import { ErrorState } from '../../../shared/components/ErrorState';
import { getApiErrorMessage } from '../../../shared/types/api';
import { useAuth } from '../../auth/hooks/useAuth';
import { NewChatButton } from '../../sessions/components/NewChatButton';
import { SessionList } from '../../sessions/components/SessionList';
import { useCreateSession } from '../../sessions/hooks/useCreateSession';
import { useDeleteSession } from '../../sessions/hooks/useDeleteSession';
import { useSessionsQuery } from '../../sessions/hooks/useSessionsQuery';
import { ChatHeader } from '../components/ChatHeader';
import { ChatInput } from '../components/ChatInput';
import { ChatLayout } from '../components/ChatLayout';
import { MessageList } from '../components/MessageList';
import { SourcesDrawer } from '../components/SourcesDrawer';
import { useMessagesQuery } from '../hooks/useMessagesQuery';
import { useSendMessageStream } from '../hooks/useSendMessageStream';

const EMPTY_SESSIONS = [];

function readSessionId(param) {
  if (!param) {
    return null;
  }

  const parsedValue = Number(param);
  return Number.isInteger(parsedValue) && parsedValue > 0 ? parsedValue : null;
}

export function ChatPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const activeSessionId = readSessionId(searchParams.get('sessionId'));

  const { logout, user } = useAuth();
  const sessionsQuery = useSessionsQuery();
  const createSessionMutation = useCreateSession();
  const deleteSessionMutation = useDeleteSession();
  const messagesQuery = useMessagesQuery(activeSessionId);
  const sendMessageStream = useSendMessageStream();

  const sessions = sessionsQuery.data ?? EMPTY_SESSIONS;
  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? null;
  const optimisticMessages = activeSessionId
    ? sendMessageStream.optimisticMessages[activeSessionId] ?? []
    : [];
  const messages = [...(messagesQuery.data ?? []), ...optimisticMessages];

  function setActiveSession(sessionId) {
    setSelectedMessage(null);
    setIsSidebarOpen(false);

    startTransition(() => {
      const nextParams = new URLSearchParams(searchParams);

      if (sessionId) {
        nextParams.set('sessionId', String(sessionId));
      } else {
        nextParams.delete('sessionId');
      }

      setSearchParams(nextParams, { replace: true });
    });
  }

  useEffect(() => {
    if (!activeSessionId && sessions.length > 0) {
      startTransition(() => {
        const nextParams = new URLSearchParams(searchParams);
        nextParams.set('sessionId', String(sessions[0].id));
        setSearchParams(nextParams, { replace: true });
      });
    }
  }, [activeSessionId, searchParams, sessions, setSearchParams]);

  async function handleCreateSession() {
    const session = await createSessionMutation.mutateAsync();
    setActiveSession(session.id);
  }

  async function handleDeleteSession(sessionId) {
    const remainingSessions = sessions.filter((session) => session.id !== sessionId);
    const shouldDelete = window.confirm('Delete this conversation?');
    if (!shouldDelete) {
      return;
    }

    await deleteSessionMutation.mutateAsync(sessionId);

    if (activeSessionId === sessionId) {
      setActiveSession(remainingSessions[0]?.id ?? null);
    }
  }

  async function handleSendMessage(message) {
    if (!activeSessionId) {
      return;
    }

    await sendMessageStream.sendMessage(activeSessionId, message);
  }

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 rounded-[1.5rem] bg-slate-900 px-4 py-4 text-white">
        <div className="flex gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-sky-500 text-sm font-semibold">
            RAG
          </div>
          <div>
            <h2 className="text-base font-semibold">Knowledge Chat</h2>
            <p className="text-xs text-slate-300">
              {user ? `Signed in as ${user.username}` : 'Authenticated workspace'}
            </p>
          </div>
        </div>

        <Button
          className="lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
          size="sm"
          type="button"
          variant="ghost"
        >
          Close
        </Button>
      </div>

      <div className="mt-4">
        <NewChatButton
          disabled={createSessionMutation.isPending}
          onClick={() => void handleCreateSession()}
        />
      </div>

      <div className="mt-4 min-h-0 flex-1 overflow-y-auto">
        {sessionsQuery.error ? (
          <ErrorState
            description={getApiErrorMessage(
              sessionsQuery.error,
              'We could not load your conversations.',
            )}
            title="Session list unavailable"
          />
        ) : (
          <SessionList
            activeSessionId={activeSessionId}
            isLoading={sessionsQuery.isLoading}
            onDeleteSession={(sessionId) => void handleDeleteSession(sessionId)}
            onSelectSession={setActiveSession}
            sessions={sessions}
          />
        )}
      </div>

      <div className="mt-4 border-t border-slate-200 pt-4">
        <Button className="w-full" onClick={() => logout()} type="button" variant="ghost">
          Log out
        </Button>
      </div>
    </div>
  );

  const main = (
    <div className="flex h-full min-h-[calc(100svh-1.5rem)] w-full min-w-0 flex-col">
      <ChatHeader
        actions={
          <div className="flex items-center gap-2">
            <Button
              className="lg:hidden"
              onClick={() => setIsSidebarOpen(true)}
              size="sm"
              type="button"
              variant="ghost"
            >
              Sessions
            </Button>
            <Button
              onClick={() => void handleCreateSession()}
              size="sm"
              type="button"
              variant="secondary"
            >
              New chat
            </Button>
          </div>
        }
        subtitle={
          activeSession
            ? 'Messages persist automatically and new responses stream into the thread.'
            : 'Create a new conversation or pick one from the sidebar to begin.'
        }
        title={activeSession?.title?.trim() || 'New conversation'}
      />

      <div className="min-h-0 flex flex-1 flex-col">
        {activeSessionId ? (
          <MessageList
            errorMessage={
              messagesQuery.error
                ? getApiErrorMessage(messagesQuery.error, 'Unable to load messages.')
                : null
            }
            isLoading={messagesQuery.isLoading}
            messages={messages}
            onOpenSources={setSelectedMessage}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center px-4 py-6 md:px-6">
            <div className="w-full max-w-2xl">
              <EmptyState
                action={
                  <Button onClick={() => void handleCreateSession()} type="button">
                    Start a new chat
                  </Button>
                }
                description="Choose an existing session from the left or create a new one to begin chatting with your retrieval-augmented assistant."
                title="No session selected"
              />
            </div>
          </div>
        )}
      </div>

      <ChatInput
        disabled={!activeSessionId}
        errorMessage={sendMessageStream.streamError}
        isSending={sendMessageStream.isSending}
        onSend={handleSendMessage}
      />

      <SourcesDrawer message={selectedMessage} onClose={() => setSelectedMessage(null)} />
    </div>
  );

  return (
    <ChatLayout
      main={main}
      onCloseSidebar={() => setIsSidebarOpen(false)}
      sidebar={sidebar}
      sidebarOpen={isSidebarOpen}
    />
  );
}
