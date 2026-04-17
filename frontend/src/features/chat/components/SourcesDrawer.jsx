import { Button } from '../../../shared/components/Button';
import { EmptyState } from '../../../shared/components/EmptyState';

export function SourcesDrawer({ message, onClose }) {
  const isOpen = Boolean(message);

  return (
    <div className={`fixed inset-0 z-50 ${isOpen ? 'pointer-events-auto' : 'pointer-events-none'}`}>
      <div
        className={`absolute inset-0 bg-slate-950/30 transition ${isOpen ? 'opacity-100' : 'opacity-0'}`}
      >
        <button className="h-full w-full" onClick={onClose} type="button" />
      </div>

      <aside
        className={`absolute right-0 top-0 h-full w-full max-w-full border-l border-slate-200 bg-white shadow-2xl transition duration-300 sm:max-w-sm md:max-w-md lg:max-w-lg xl:max-w-xl ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-4 md:px-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-600">
              Sources
            </p>
            <h2 className="mt-1 text-xl font-semibold text-slate-900">Retrieved context</h2>
          </div>
          <Button onClick={onClose} type="button" variant="ghost">
            Close
          </Button>
        </div>

        <div className="h-[calc(100%-81px)] overflow-y-auto px-4 py-5 md:px-5">
          {message?.sourceContext ? (
            <section className="mb-5 rounded-3xl border border-sky-100 bg-sky-50 p-4 text-sm text-slate-700">
              <p>
                Retrieved chunks:{' '}
                <strong>{message.sourceContext.retrievedChunkCount ?? 'Unknown'}</strong>
              </p>
              {message.sourceContext.topics?.length ? (
                <p className="mt-2">Topics: {message.sourceContext.topics.join(', ')}</p>
              ) : null}
            </section>
          ) : null}

          {message?.sources?.length ? (
            <div className="space-y-4">
              {message.sources.map((source) => (
                <article
                  className="rounded-3xl border border-slate-200 bg-slate-50 p-4"
                  key={source.id ?? source.chunk_index ?? source.text}
                >
                  <div className="flex flex-col gap-1 text-xs font-medium uppercase tracking-[0.12em] text-slate-500">
                    <span>{source.topic ?? 'Unknown topic'}</span>
                    <span>{source.source ?? 'Unknown source'}</span>
                  </div>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                    {source.text}
                  </p>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              description="This backend currently streams retrieval metadata, but it does not always return raw chunk payloads for persisted messages."
              title="Detailed sources are unavailable for this reply"
            />
          )}
        </div>
      </aside>
    </div>
  );
}
