/** Az oldal VÁZA: amit azonnal látni lehet, amíg a tényleges tartalom betölt.
 *
 * Miért kell? Mert a Next.js szerver-komponensei az adatok megérkezéséig NEM
 * rajzolnak semmit: egy menüpontra kattintva a RÉGI oldal maradt a képernyőn,
 * mozdulatlanul, amíg a szerver végzett. Kívülről ez úgy néz ki, hogy "a
 * rendszer nem reagál" - pedig dolgozik. Ez a váz azonnal megjelenik
 * (lásd app/(app)/loading.tsx), és a valódi tartalom a helyére csúszik, amint
 * kész.
 *
 * Szándékosan a valódi elrendezést utánozza (felső sáv, cím, kártyák, sorok),
 * nem egy pörgő ikon: így nem "ugrik" a képernyő, amikor megjön a tartalom. */
export function OldalVaz({ sorok = 8 }: { sorok?: number }) {
  return (
    <div className="flex flex-1 animate-pulse flex-col" aria-busy="true" aria-label="Betöltés">
      {/* felső sáv */}
      <div className="flex items-center justify-between gap-4 border-b border-border px-8 py-5">
        <div className="space-y-2">
          <div className="h-4 w-48 rounded bg-surface-3" />
          <div className="h-3 w-32 rounded bg-surface-3/70" />
        </div>
        <div className="h-8 w-64 rounded-[var(--radius)] bg-surface-3" />
      </div>

      <div className="flex-1 space-y-6 p-8">
        {/* kártya-fejléc + szűrősor */}
        <div className="rounded-[var(--radius-lg)] border border-border p-5">
          <div className="mb-5 h-4 w-40 rounded bg-surface-3" />
          <div className="mb-5 flex gap-2">
            <div className="h-8 w-64 rounded-[var(--radius)] bg-surface-3" />
            <div className="h-8 w-24 rounded-[var(--radius)] bg-surface-3/70" />
          </div>
          <div className="space-y-2.5">
            {Array.from({ length: sorok }).map((_, i) => (
              <div key={i} className="flex gap-3">
                <div className="h-4 flex-1 rounded bg-surface-3/80" />
                <div className="h-4 w-1/5 rounded bg-surface-3/60" />
                <div className="h-4 w-1/6 rounded bg-surface-3/60" />
                <div className="h-4 w-24 rounded bg-surface-3/60" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Egy kártyányi váz - a Suspense-szel streamelt szekciókhoz (pl. egy lassú
 * táblázat), ahol az oldal többi része már ott van. */
export function KartyaVaz({ sorok = 6, cim }: { sorok?: number; cim?: string }) {
  return (
    <div className="animate-pulse rounded-[var(--radius-lg)] border border-border p-5" aria-busy="true">
      <div className="mb-5 h-4 w-40 rounded bg-surface-3">{cim ? <span className="sr-only">{cim}</span> : null}</div>
      <div className="space-y-2.5">
        {Array.from({ length: sorok }).map((_, i) => (
          <div key={i} className="flex gap-3">
            <div className="h-4 flex-1 rounded bg-surface-3/80" />
            <div className="h-4 w-1/5 rounded bg-surface-3/60" />
            <div className="h-4 w-24 rounded bg-surface-3/60" />
          </div>
        ))}
      </div>
    </div>
  );
}
