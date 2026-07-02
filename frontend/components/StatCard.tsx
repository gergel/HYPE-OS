type Tone = "default" | "danger";

export function StatCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: Tone;
}) {
  const isDanger = tone === "danger";
  return (
    <div
      className={`rounded-[var(--radius)] p-4 ${isDanger ? "bg-bg-danger" : "bg-surface-1"}`}
    >
      <p className={`mb-1 text-[13px] ${isDanger ? "text-text-danger" : "text-text-secondary"}`}>{label}</p>
      <p className={`text-2xl font-medium ${isDanger ? "text-text-danger" : "text-text-primary"}`}>{value}</p>
    </div>
  );
}
