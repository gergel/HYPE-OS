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
}: {
  label: string;
  value: string | number;
  tone?: Tone;
  href?: string;
  icon?: LucideIcon;
}) {
  const cls = TONE_CLASSES[tone];
  const content = (
    <>
      {Icon && (
        <div className={`mb-3 flex h-9 w-9 items-center justify-center rounded-[var(--radius)] ${cls.bg}`}>
          <Icon size={17} strokeWidth={2} className={cls.icon} aria-hidden />
        </div>
      )}
      <p className="mb-1 text-[13px] text-text-secondary">{label}</p>
      <p className={`text-2xl font-semibold ${cls.text}`}>{value}</p>
    </>
  );
  const className = `block rounded-[var(--radius-lg)] border border-border p-4 transition-colors ${
    Icon ? "bg-surface-2" : tone === "danger" ? "bg-bg-danger" : "bg-surface-1"
  } ${href ? "hover:border-text-accent/40" : ""}`;

  if (href) {
    return (
      <Link href={href} className={className}>
        {content}
      </Link>
    );
  }
  return <div className={className}>{content}</div>;
}
