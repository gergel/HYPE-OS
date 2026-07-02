type Tone = "success" | "warning" | "danger" | "neutral";

const toneClasses: Record<Tone, string> = {
  success: "bg-bg-success text-text-success",
  warning: "bg-bg-warning text-text-warning",
  danger: "bg-bg-danger text-text-danger",
  neutral: "bg-surface-3 text-text-secondary",
};

export function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  return (
    <span className={`rounded-[var(--radius)] px-2.5 py-1 text-xs ${toneClasses[tone]}`}>{label}</span>
  );
}
