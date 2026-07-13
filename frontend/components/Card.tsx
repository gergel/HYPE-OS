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
    <div
      className={`rounded-[var(--radius-lg)] border border-border bg-surface-2 p-5 shadow-[0_1px_0_rgba(255,255,255,0.03)_inset,0_8px_24px_-16px_rgba(0,0,0,0.6)] ${className}`}
    >
      {title && <p className="mb-3 text-sm font-medium text-text-primary">{title}</p>}
      {children}
    </div>
  );
}
