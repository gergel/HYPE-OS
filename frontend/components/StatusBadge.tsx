type Tone = "success" | "warning" | "danger" | "neutral" | "accent" | "blue" | "teal" | "orange" | "pink";

const toneClasses: Record<Tone, string> = {
  success: "bg-bg-success text-text-success",
  warning: "bg-bg-warning text-text-warning",
  danger: "bg-bg-danger text-text-danger",
  neutral: "bg-surface-3 text-text-secondary",
  accent: "bg-bg-accent text-text-accent",
  blue: "bg-bg-blue text-text-blue",
  teal: "bg-bg-teal text-text-teal",
  orange: "bg-bg-orange text-text-orange",
  pink: "bg-bg-pink text-text-pink",
};

export function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  return <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${toneClasses[tone]}`}>{label}</span>;
}
