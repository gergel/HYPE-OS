import { CalendarClock, FileText } from "lucide-react";
import type { SajatDiszpo } from "@/lib/api";

/** MAI/HOLNAPI DISZPÓD - nagy, kiemelt kártya a dashboard tetején annak, aki
 * egy mai vagy holnapi forgatás stábjában van (a felhasználó kérése). Csak a
 * projekt neve, a dátum és a diszpó PDF-je látszik - a diszpó semmilyen más
 * adata nem. A gomb a PDF-et nagyban (új lapon) nyitja meg. */
export function SajatDiszpoKartya({ diszpok }: { diszpok: SajatDiszpo[] }) {
  if (diszpok.length === 0) return null;

  const ma = new Date();
  const maNap = isoNap(ma);
  const holnapNap = isoNap(new Date(ma.getFullYear(), ma.getMonth(), ma.getDate() + 1));

  const sorok = diszpok
    .map((d) => {
      if (!d.forgatas_datuma) return null;
      const kezdet = d.forgatas_datuma.slice(0, 10);
      const veg = (d.forgatas_vege ?? d.forgatas_datuma).slice(0, 10);
      // Ma zajló (akár több napos) forgatás = MAI; ami csak holnap kezdődik
      // (vagy holnap is tart, de ma még nem), az a HOLNAPI.
      if (kezdet <= maNap && maNap <= veg) return { ...d, melyik: "MAI DISZPÓD" as const };
      if (kezdet <= holnapNap && holnapNap <= veg) return { ...d, melyik: "HOLNAPI DISZPÓD" as const };
      return null;
    })
    .filter((d): d is SajatDiszpo & { melyik: "MAI DISZPÓD" | "HOLNAPI DISZPÓD" } => d !== null)
    .sort((a, b) => (a.melyik === b.melyik ? 0 : a.melyik === "MAI DISZPÓD" ? -1 : 1));

  if (sorok.length === 0) return null;

  return (
    <div className="space-y-3">
      {sorok.map((d) => (
        <div
          key={d.project_id}
          className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--radius)] border-2 border-text-accent/60 bg-surface-1 p-4 md:p-5"
        >
          <div className="min-w-0">
            <p className="flex items-center gap-2 text-[13px] font-bold uppercase tracking-widest text-text-accent">
              <CalendarClock size={16} />
              {d.melyik}
            </p>
            <p className="mt-1 truncate text-[18px] font-semibold text-text-primary">
              {d.projekt_nev ?? `Forgatás #${d.project_id}`}
            </p>
            <p className="text-[13px] text-text-secondary">
              {datumSzoveg(d.forgatas_datuma)}
              {d.forgatas_vege && d.forgatas_vege !== d.forgatas_datuma
                ? ` – ${datumSzoveg(d.forgatas_vege)}`
                : ""}
            </p>
          </div>
          {d.pdf_url ? (
            <a
              href={d.pdf_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex shrink-0 items-center gap-2 rounded-[var(--radius)] bg-text-accent px-4 py-2.5 text-[14px] font-semibold text-surface-1 hover:opacity-90"
            >
              <FileText size={16} />
              Diszpó PDF megnyitása
            </a>
          ) : (
            <span className="shrink-0 text-[13px] text-text-muted">A diszpó PDF még nem érhető el.</span>
          )}
        </div>
      ))}
    </div>
  );
}

function isoNap(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function datumSzoveg(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("hu-HU") : "";
}
