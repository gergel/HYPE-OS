import type { LucideIcon } from "lucide-react";
import Link from "next/link";

type Tone = "default" | "danger" | "accent" | "blue" | "teal" | "orange" | "pink";

const TONE_CLASSES: Record<Tone, { bg: string; text: string; icon: string }> = {
  default: { bg: "bg-surface-3", text: "text-text-primary", icon: "text-text-secondary" },
  danger: { bg: "bg-bg-danger", text: "text-text-danger", icon: "text-text-danger" },
  accent: { bg: "bg-bg-accent", text: "text-text-primary", icon: "text-text-accent" },
  blue: { bg: "bg-bg-blue", text: "text-text-primary", icon: "text-text-blue" },
  teal: { bg: "bg-bg-teal", text: "text-text-primary", icon: "text-text-teal" },
  orange: { bg: "bg-bg-orange", text: "text-text-primary", icon: "text-text-orange" },
  pink: { bg: "bg-bg-pink", text: "text-text-primary", icon: "text-text-pink" },
};

export function StatCard({
  label,
  value,
  tone = "default",
  href,
  icon: Icon,
  /** Halvány másodlagos sor a szám ALATT - arra való, hogy a fő szám mellé
   * odakerüljön a másik nézőpont (pl. "bruttó: 1 270 000 Ft"), anélkül hogy
   * versenyezne vele. */
  megjegyzes,
}: {
  label: string;
  value: string | number;
  tone?: Tone;
  href?: string;
  icon?: LucideIcon;
  megjegyzes?: string;
}) {
  const cls = TONE_CLASSES[tone];
  const content = (
    <>
      {Icon && (
        <div
          className={`mb-4 flex h-8 w-8 items-center justify-center rounded-[var(--radius)] border border-border ${cls.bg}`}
        >
          <Icon size={15} strokeWidth={1.75} className={cls.icon} aria-hidden />
        </div>
      )}
      <p className="mb-2 text-[12.5px] leading-snug text-text-secondary">{label}</p>
      {/* A szám a kártya tárgya - tabuláris számjegyekkel, hogy egymás alatt
          a számok oszlopba rendeződjenek, ne ugráljanak. */}
      <p className={`text-[26px] font-semibold leading-none tracking-[-0.03em] tabular-nums ${cls.text}`}>{value}</p>
      {megjegyzes && <p className="mt-2 text-[11.5px] leading-snug text-text-muted tabular-nums">{megjegyzes}</p>}
    </>
  );
  const className = `block rounded-[var(--radius-lg)] border border-border p-5 transition-colors duration-200 ${
    tone === "danger" && !Icon ? "bg-bg-danger" : "bg-surface-2"
  } ${href ? "hover:border-border-strong hover:bg-surface-3" : ""}`;

  if (href) {
    return (
      <Link href={href} className={className}>
        {content}
      </Link>
    );
  }
  return <div className={className}>{content}</div>;
}
