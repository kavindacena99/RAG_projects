export function ErrorState({ action, description, title }) {
  return (
    <div
      className="rounded-3xl border border-rose-200 bg-rose-50 p-5 text-left shadow-sm"
      role="alert"
    >
      <h3 className="text-base font-semibold text-rose-900">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-rose-700">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
