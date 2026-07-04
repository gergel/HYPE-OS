import Link from "next/link";

type Tone = "default" | "danger";

export function StatCard({
  label,
  value,
  tone = "default",
  href,
}: {
  label: string;
  value: string | number;
  tone?: Tone;
  href?: string;
}) {
  const isDanger = tone === "danger";
  const content = (
    <>
      <p className={`mb-1 text-[13px] ${isDanger ? "text-text-danger" : "text-text-secondary"}`}>{label}</p>
      <p className={`text-2xl font-medium ${isDanger ? "text-text-danger" : "text-text-primary"}`}>{value}</p>
    </>
  );
  const className = `block rounded-[var(--radius)] p-4 transition-colors ${
    isDanger ? "bg-bg-danger" : "bg-surface-1"
  } ${href ? "hover:ring-1 hover:ring-border" : ""}`;

  if (href) {
    return (
      <Link href={href} className={className}>
        {content}
      </Link>
    );
  }
  return <div className={className}>{content}</div>;
}
