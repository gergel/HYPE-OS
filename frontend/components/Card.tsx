export function Card({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-[var(--radius-lg)] border border-border bg-surface-2 p-5 ${className}`}>
      {title && <p className="mb-3 text-sm font-medium text-text-primary">{title}</p>}
      {children}
    </div>
  );
}
