export function Spinner({ label }) {
  return (
    <div className="inline-flex items-center gap-2 text-sm text-slate-500" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-sky-500" />
      {label ? <span>{label}</span> : null}
    </div>
  );
}
