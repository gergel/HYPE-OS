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

/** Állapotjelző. A szín az ADAT hordozója - ezért a badge maga visszafogott:
 * halvány háttér, keret nélkül, a jelentést a szövegszín adja. */
export function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-[3px] text-[12px] font-medium tracking-[-0.005em] ${toneClasses[tone]}`}
    >
      {label}
    </span>
  );
}
