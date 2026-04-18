import { ThemeToggle } from '../../../shared/components/ThemeToggle';

export function AuthLayout({
  children,
  description,
  eyebrow,
  title,
}) {
  return (
    <main className="mx-auto flex h-full min-h-0 w-full max-w-7xl flex-col gap-6 overflow-y-auto px-4 py-6 md:px-6 lg:flex-row lg:items-stretch lg:py-10">
      <section className="flex flex-1 flex-col justify-between rounded-[2rem] border border-white/60 bg-slate-900 px-6 py-8 text-white shadow-[0_30px_80px_rgba(15,23,42,0.18)] dark:border-slate-800 dark:bg-slate-950 md:px-8 lg:min-h-[calc(100vh-5rem)] lg:px-10">
        <div>
          <div className="flex justify-end">
            <ThemeToggle />
          </div>
          <span className="inline-flex rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-sky-100">
            {eyebrow}
          </span>
          <h1 className="mt-5 max-w-xl text-4xl font-semibold tracking-tight sm:text-5xl">
            {title}
          </h1>
          <p className="mt-4 max-w-xl text-base leading-7 text-slate-300">{description}</p>
        </div>

        <div className="mt-10 rounded-[1.75rem] border border-white/10 bg-white/5 p-6 backdrop-blur">
          <h2 className="text-xl font-semibold text-white">Built for grounded AI conversations</h2>
          <p className="mt-3 text-sm leading-7 text-slate-300">
            Resume past chats, stream answers as they are generated, and keep the
            interface ready for source-backed retrieval without mixing transport logic
            into the UI.
          </p>
        </div>
      </section>

      <section className="flex w-full max-w-xl items-center justify-center lg:w-[430px]">
        {children}
      </section>
    </main>
  );
}
