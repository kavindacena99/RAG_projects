export function ChatHeader({ actions, subtitle, title }) {
  return (
    <header className="border-b border-slate-200 px-4 py-4 md:px-6">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-600">
            Workspace chat
          </p>
          <h1 className="mt-2 truncate text-xl font-semibold tracking-tight text-slate-900 md:text-2xl">
            {title}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">{subtitle}</p>
        </div>
        {actions ? <div className="shrink-0">{actions}</div> : null}
      </div>
    </header>
  );
}
