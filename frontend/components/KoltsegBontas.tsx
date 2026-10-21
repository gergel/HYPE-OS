import { formatHuf } from "@/lib/api";

/** Mire ment el a pénz ezen a projektkódon - a négy rész, aminek az összege
 * pontosan az "Összes költség".
 *
 * Külön kártya, mert az összeg önmagában nem mond semmit: 157 ezer forint
 * teljesen mást jelent, ha a külsős stábra ment, mint ha a saját emberünk
 * munkanapjai. A számítás a backendben van (models/project_code.py), itt csak
 * megjelenítjük - így a lista és az adatlap ugyanazt a négy számot mutatja.
 *
 * A sávok arányosak, hogy ránézésre is látszódjon, mi viszi a pénzt. Nulla
 * összegű rész nem jelenik meg: egy csupa "0 Ft" lista csak elfedi azt a
 * kettőt, ami tényleg számít. */
export function KoltsegBontas({
  kulsos,
  egyeb,
  vagas,
  belsos,
  osszesen,
}: {
  kulsos: number;
  egyeb: number;
  vagas: number;
  belsos: number;
  osszesen: number;
}) {
  const reszek = [
    { cimke: "Külsős stáb", ertek: kulsos, szin: "bg-text-accent" },
    { cimke: "Vágás (utómunka)", ertek: vagas, szin: "bg-text-teal" },
    {
      cimke: "Belsős munkanapok",
      ertek: belsos,
      szin: "bg-text-orange",
      megjegyzes: "nincs kiadás-sora, a havi bér a hónap végén megy be egyben",
    },
    { cimke: "Egyéb kiadás", ertek: egyeb, szin: "bg-text-pink" },
  ].filter((r) => r.ertek > 0);

  if (reszek.length === 0) return null;

  return (
    <div className="rounded-[var(--radius-xl)] border border-border bg-surface-2 p-5">
      <p className="mb-3 text-[12.5px] text-text-secondary">Mibe került (a költség bontása)</p>
      <ul className="space-y-2.5">
        {reszek.map((r) => (
          <li key={r.cimke} className="flex items-baseline gap-3">
            <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${r.szin}`} aria-hidden />
            <span className="min-w-[9.5rem] text-[13px] text-text-primary">{r.cimke}</span>
            <span className="tabular-nums text-[13px] text-text-primary">{formatHuf(r.ertek)}</span>
            <span className="text-[12px] text-text-muted">
              {osszesen > 0 ? `${Math.round((r.ertek / osszesen) * 100)}%` : ""}
              {r.megjegyzes ? ` - ${r.megjegyzes}` : ""}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 border-t border-border pt-3 text-[13px] text-text-secondary">
        Összesen: <span className="tabular-nums text-text-primary">{formatHuf(osszesen)}</span>
      </p>
    </div>
  );
}
