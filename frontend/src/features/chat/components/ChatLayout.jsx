import { cn } from '../../../shared/utils/cn';

export function ChatLayout({ main, onCloseSidebar, sidebar, sidebarOpen }) {
  return (
    <main className="mx-auto flex h-full min-h-0 w-full max-w-7xl px-3 py-3 md:px-5 md:py-5 lg:gap-5 lg:px-6">
      <div
        className={cn(
          'fixed inset-0 z-40 lg:hidden',
          sidebarOpen ? 'pointer-events-auto' : 'pointer-events-none',
        )}
      >
        <button
          aria-label="Close conversations"
          className={cn(
            'absolute inset-0 bg-slate-950/35 transition',
            sidebarOpen ? 'opacity-100' : 'opacity-0',
          )}
          onClick={onCloseSidebar}
          type="button"
        />
        <aside
          className={cn(
            'absolute left-0 top-0 flex h-full w-[88vw] max-w-sm flex-col border-r border-slate-200 bg-slate-50 p-4 shadow-2xl transition duration-300 dark:border-slate-800 dark:bg-slate-950',
            sidebarOpen ? 'translate-x-0' : '-translate-x-full',
          )}
        >
          {sidebar}
        </aside>
      </div>

      <aside className="hidden h-full min-h-0 w-[300px] shrink-0 rounded-[2rem] border border-white/70 bg-white/70 p-4 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur dark:border-slate-800/80 dark:bg-slate-950/75 dark:shadow-[0_24px_60px_rgba(2,6,23,0.45)] lg:flex xl:w-[340px]">
        {sidebar}
      </aside>
      <section className="flex h-full min-h-0 w-full min-w-0 flex-1 overflow-hidden rounded-[2rem] border border-white/70 bg-white/80 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur dark:border-slate-800/80 dark:bg-slate-950/75 dark:shadow-[0_24px_60px_rgba(2,6,23,0.45)]">
        {main}
      </section>
    </main>
  );
}
