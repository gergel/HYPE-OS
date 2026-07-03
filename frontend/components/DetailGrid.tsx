import type { ReactNode } from "react";

export function DetailGrid({ fields }: { fields: { label: string; value: ReactNode; wide?: boolean }[] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
      {fields.map((f) => (
        <div key={f.label} className={f.wide ? "sm:col-span-2 lg:col-span-3" : undefined}>
          <dt className="text-[12px] text-text-muted">{f.label}</dt>
          <dd className="mt-0.5 text-[13px] leading-relaxed text-text-primary break-words">{f.value ?? "–"}</dd>
        </div>
      ))}
    </dl>
  );
}
