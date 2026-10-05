export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p className="status-line">
      <span className="status-dot checking" />
      {label}
    </p>
  );
}

export function ErrorNotice({ message }: { message: string }) {
  return <p className="error-text">{message}</p>;
}

export function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>;
}
