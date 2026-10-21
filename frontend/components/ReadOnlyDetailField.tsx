/** Egy önálló, csak olvasható mező-doboz, ugyanabban a "boxed" stílusban, mint
 * a generikus EditableDetailGrid (lásd components/EditableDetailGrid.tsx) -
 * olyan mezőkhöz, amik nem valódi, PATCH-elhető szöveg/szám oszlopok (pl. egy
 * idegen kulcs, amit már NÉVRE feloldva mutatunk), ezért nem mehetnek át a
 * generikus mezőrácson (lásd app/(app)/hype-todo-lista/[id]/page.tsx,
 * app/(app)/flora/[id]/page.tsx - a "ki vezette fel"/"felelős" mezők). */
export function ReadOnlyDetailField({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex flex-col gap-1.5">
      <dt className="t-label">{label}</dt>
      <dd className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 min-h-[38px] text-[13px] leading-relaxed text-text-primary break-words">
        {value ?? "Üres"}
      </dd>
    </div>
  );
}
