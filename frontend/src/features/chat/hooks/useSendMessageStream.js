import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { getApiErrorMessage } from '../../../shared/types/api';
import { SESSIONS_QUERY_KEY } from '../../sessions/hooks/useSessionsQuery';
import { sendMessageStream } from '../api/chatApi';
import { messagesQueryKey } from './useMessagesQuery';
import { extractSourceContext, extractSourcesFromMetadata } from '../utils/sourceUtils';

export const DRAFT_SESSION_KEY = 'draft';

function patchSessionMessages(currentMap, sessionId, updater) {
  const nextMessages = updater(currentMap[sessionId] ?? []);
  const nextMap = { ...currentMap };

  if (nextMessages.length === 0) {
    delete nextMap[sessionId];
  } else {
    nextMap[sessionId] = nextMessages;
  }

  return nextMap;
}

function moveSessionMessages(currentMap, fromSessionId, toSessionId) {
  if (fromSessionId === toSessionId || !currentMap[fromSessionId]?.length) {
    return currentMap;
  }

  const nextMap = { ...currentMap };
  const existingTargetMessages = nextMap[toSessionId] ?? [];
  nextMap[toSessionId] = [...existingTargetMessages, ...nextMap[fromSessionId]];
  delete nextMap[fromSessionId];
  return nextMap;
}

function readSessionId(value) {
  const parsedValue = Number(value);
  return Number.isInteger(parsedValue) && parsedValue > 0 ? parsedValue : null;
}

function parseSseEvents(buffer) {
  const blocks = buffer.split('\n\n');
  const remaining = blocks.pop() ?? '';
  const events = [];

  for (const block of blocks) {
    const payload = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('\n');

    if (!payload) {
      continue;
    }

    events.push(JSON.parse(payload));
  }

  return { events, remaining };
}

export function useSendMessageStream() {
  const queryClient = useQueryClient();
  const [optimisticMessages, setOptimisticMessages] = useState({});
  const [sendingSessionId, setSendingSessionId] = useState(null);
  const [streamError, setStreamError] = useState(null);

  async function sendMessage({ message, onSessionReady, sessionId = null }) {
    const trimmedMessage = message.trim();
    const sessionKey = sessionId ?? DRAFT_SESSION_KEY;

    if (!trimmedMessage || sendingSessionId !== null) {
      return;
    }

    setStreamError(null);
    setSendingSessionId(sessionKey);

    const timestamp = new Date().toISOString();
    const uniqueId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const tempUserId = `temp-user-${uniqueId}`;
    const tempAssistantId = `temp-assistant-${uniqueId}`;
    let resolvedSessionId = sessionId;
    let optimisticSessionKey = sessionKey;

    setOptimisticMessages((currentMap) =>
      patchSessionMessages(currentMap, sessionKey, (messages) => [
        ...messages,
        {
          content: trimmedMessage,
          created_at: timestamp,
          id: tempUserId,
          isTemporary: true,
          role: 'user',
          sourceContext: null,
          sources: [],
        },
        {
          content: '',
          created_at: timestamp,
          id: tempAssistantId,
          isStreaming: true,
          isTemporary: true,
          role: 'assistant',
          sourceContext: null,
          sources: [],
        },
      ]),
    );

    try {
      const response = await sendMessageStream({
        message: trimmedMessage,
        session_id: sessionId,
      });

      if (!response.body) {
        throw new Error('The response stream was not available.');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let sawDone = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSseEvents(buffer);
        buffer = parsed.remaining;

        for (const event of parsed.events) {
          const streamedSessionId = readSessionId(event.session_id);
          if (!resolvedSessionId && streamedSessionId) {
            resolvedSessionId = streamedSessionId;
          }

          if (event.type === 'metadata') {
            const sources = extractSourcesFromMetadata(event);
            const sourceContext = extractSourceContext(event);

            setOptimisticMessages((currentMap) =>
              patchSessionMessages(currentMap, optimisticSessionKey, (messages) =>
                messages.map((existingMessage) =>
                  existingMessage.id === tempAssistantId
                    ? { ...existingMessage, sourceContext, sources }
                    : existingMessage,
                ),
              ),
            );
          }

          if (event.type === 'token') {
            setOptimisticMessages((currentMap) =>
              patchSessionMessages(currentMap, optimisticSessionKey, (messages) =>
                messages.map((existingMessage) =>
                  existingMessage.id === tempAssistantId
                    ? {
                        ...existingMessage,
                        content: `${existingMessage.content}${event.content}`,
                      }
                    : existingMessage,
                ),
              ),
            );
          }

          if (event.type === 'done') {
            sawDone = true;
            const doneSessionId = readSessionId(event.session_id);

            if (!resolvedSessionId && doneSessionId) {
              resolvedSessionId = doneSessionId;
            }

            if (optimisticSessionKey === DRAFT_SESSION_KEY && resolvedSessionId) {
              setOptimisticMessages((currentMap) =>
                moveSessionMessages(currentMap, DRAFT_SESSION_KEY, resolvedSessionId),
              );
              optimisticSessionKey = resolvedSessionId;
            }

            setOptimisticMessages((currentMap) =>
              patchSessionMessages(currentMap, optimisticSessionKey, (messages) =>
                messages.map((existingMessage) =>
                  existingMessage.id === tempAssistantId
                    ? {
                        ...existingMessage,
                        content: event.content,
                        isStreaming: false,
                        sourceContext:
                          extractSourceContext(event) ?? existingMessage.sourceContext,
                        sources:
                          extractSourcesFromMetadata(event).length > 0
                            ? extractSourcesFromMetadata(event)
                            : existingMessage.sources,
                      }
                    : existingMessage,
                ),
              ),
            );

            if (event.title && resolvedSessionId) {
              queryClient.setQueryData(SESSIONS_QUERY_KEY, (currentSessions = []) =>
                currentSessions.map((session) =>
                  session.id === resolvedSessionId ? { ...session, title: event.title } : session,
                ),
              );
            }

            if (resolvedSessionId) {
              onSessionReady?.(resolvedSessionId);
            }
          }

          if (event.type === 'error') {
            throw new Error(event.detail);
          }
        }
      }

      buffer += decoder.decode();
      const trailing = parseSseEvents(buffer);
      for (const event of trailing.events) {
        if (event.type === 'done') {
          sawDone = true;
        }

        if (event.type === 'error') {
          throw new Error(event.detail);
        }
      }

      if (!sawDone) {
        throw new Error('The assistant response ended before completion.');
      }

      const finalSessionId = resolvedSessionId ?? sessionId;
      const messagesKey = finalSessionId ?? sessionKey;

      await Promise.all([
        finalSessionId
          ? queryClient.invalidateQueries({ queryKey: messagesQueryKey(finalSessionId) })
          : Promise.resolve(),
        queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY }),
      ]);
      if (finalSessionId) {
        await queryClient.refetchQueries({
          queryKey: messagesQueryKey(finalSessionId),
          type: 'active',
        });
      }

      setOptimisticMessages((currentMap) =>
        patchSessionMessages(currentMap, messagesKey, (messages) =>
          messages.filter(
            (existingMessage) =>
              existingMessage.id !== tempAssistantId && existingMessage.id !== tempUserId,
          ),
        ),
      );
    } catch (error) {
      const errorMessage = getApiErrorMessage(
        error,
        'The response stream was interrupted. Please try again.',
      );
      const currentMessagesKey = optimisticSessionKey;

      setStreamError(errorMessage);
      if (sessionId) {
        await queryClient.invalidateQueries({ queryKey: messagesQueryKey(sessionId) });
        await queryClient.refetchQueries({
          queryKey: messagesQueryKey(sessionId),
          type: 'active',
        });
      }
      await queryClient.invalidateQueries({ queryKey: SESSIONS_QUERY_KEY });

      setOptimisticMessages((currentMap) =>
        patchSessionMessages(currentMap, currentMessagesKey, (messages) =>
          messages
            .filter((existingMessage) => existingMessage.id !== tempUserId)
            .map((existingMessage) =>
              existingMessage.id === tempAssistantId
                ? {
                    ...existingMessage,
                    content: errorMessage,
                    error: errorMessage,
                    isStreaming: false,
                  }
                : existingMessage,
            ),
        ),
      );
    } finally {
      setSendingSessionId(null);
    }
  }

  return {
    isSending: sendingSessionId !== null,
    optimisticMessages,
    sendMessage,
    sendingSessionId,
    streamError,
  };
}
