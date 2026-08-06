import Link from "next/link";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate, type UtokovetesOverview } from "@/lib/api";

/** Melyik fázisban áll egy projekt utóélete.
 *
 * A sorrend a folyamat sorrendje: előbb mindenkinek szerződés kell, utána jön
 * a TIG, végül az utalás. Egy projekt mindig a LEGKORÁBBI hiányzó fázisban
 * van - így a táblán balról jobbra haladva látszik, mi a következő teendő. */
export type Fazis = "szerzodes" | "tig" | "utalas" | "kesz";

export const FAZISOK: { kulcs: Fazis; cim: string; leiras: string }[] = [
  { kulcs: "szerzodes", cim: "Szerződés hiányzik", leiras: "Van, akinek még nincs meg az eseti szerződése." },
  { kulcs: "tig", cim: "Már csak TIG kell", leiras: "A szerződések megvannak, a teljesítési igazolás hiányzik." },
  { kulcs: "utalas", cim: "Utalásra vár", leiras: "A papírok megvannak, a kifizetés még hátravan." },
  { kulcs: "kesz", cim: "Kész", leiras: "Szerződés, TIG és kifizetés is megvan." },
];

export function fazisa(sor: UtokovetesOverview): Fazis {
  if (sor.szerzodes_fuggo > 0) return "szerzodes";
  if (sor.tig_fuggo > 0) return "tig";
  if (sor.kifizetes_fuggo > 0) return "utalas";
  return "kesz";
}

/** Mi hiányzik pontosan - a kártyán egy sorban. */
export function hianyzik(sor: UtokovetesOverview): string {
  switch (fazisa(sor)) {
    case "szerzodes":
      return `${sor.szerzodes_fuggo} / ${sor.szerzodes_osszes} szerződés hiányzik`;
    case "tig":
      return `${sor.tig_fuggo} / ${sor.tig_osszes} TIG hiányzik`;
    case "utalas":
      return `${sor.kifizetes_fuggo} / ${sor.kifizetes_osszes} kifizetés hátravan`;
    default:
      return sor.kifizetes_osszes === 0 ? "Nincs kifizetendő alvállalkozó" : "Mindenki ki van fizetve";
  }
}

function szerzodesBadge(osszes: number, fuggo: number) {
  if (osszes === 0) return <StatusBadge label="Nincs érintett" tone="neutral" />;
  if (fuggo === 0) return <StatusBadge label={`${osszes}/${osszes} kész`} tone="success" />;
  return <StatusBadge label={`${fuggo} függő`} tone="warning" />;
}

function tigBadge(ready: boolean, osszes: number, fuggo: number) {
  if (osszes === 0) return <StatusBadge label="Nincs érintett" tone="neutral" />;
  if (!ready) return <StatusBadge label="Szerződésre vár" tone="neutral" />;
  if (fuggo === 0) return <StatusBadge label={`${osszes}/${osszes} kész`} tone="success" />;
  return <StatusBadge label={`${fuggo} függő`} tone="warning" />;
}

function kifizetesBadge(osszes: number, fuggo: number) {
  if (osszes === 0) return <StatusBadge label="Nincs érintett" tone="neutral" />;
  if (fuggo === 0) return <StatusBadge label={`${osszes}/${osszes} kifizetve`} tone="success" />;
  return <StatusBadge label={`${fuggo} kifizetetlen`} tone="warning" />;
}

function visszajelzesBadge(darab: number) {
  if (darab === 0) return <StatusBadge label="Nincs válasz" tone="neutral" />;
  return <StatusBadge label={`${darab} válasz`} tone="success" />;
}

/** Az "admin" nézet: minden projekt egy sorban, minden fázis állapotával -
 * szűrhető és rendezhető. Ez a részletes kép; a fázisokra bontott tábla (lásd
 * UtokovetesTabla) az alap. */
export function UtokovetesLista({ rows }: { rows: UtokovetesOverview[] }) {
  return (
    <DataTable<UtokovetesOverview & { id: number }>
      filterable
      rows={rows.map((r) => ({ ...r, id: r.project_id }))}
      emptyText="Nincs még diszpózott projekt."
      getHref={(r) => `/utokovetes/${r.project_id}`}
      columns={[
        { header: "Projekt", render: (r) => r.project_nev ?? `#${r.project_id}`, sortAccessor: (r) => r.project_nev },
        { header: "Projektkód", render: (r) => r.projektkod ?? "–", sortAccessor: (r) => r.projektkod },
        {
          header: "Forgatás dátuma",
          render: (r) => formatDate(r.forgatas_datuma),
          sortAccessor: (r) => r.forgatas_datuma,
        },
        {
          header: "Szerződések",
          render: (r) => szerzodesBadge(r.szerzodes_osszes, r.szerzodes_fuggo),
          sortAccessor: (r) => r.szerzodes_fuggo,
        },
        {
          header: "Teljesítési igazolások",
          render: (r) => tigBadge(r.tig_ready, r.tig_osszes, r.tig_fuggo),
          sortAccessor: (r) => r.tig_fuggo,
        },
        {
          header: "Kifizetés",
          render: (r) => kifizetesBadge(r.kifizetes_osszes, r.kifizetes_fuggo),
          sortAccessor: (r) => r.kifizetes_fuggo,
        },
        {
          header: "Visszajelzés",
          render: (r) => visszajelzesBadge(r.visszajelzes_darab),
          sortAccessor: (r) => r.visszajelzes_darab,
        },
        {
          // Állapot-oszlop ("Kész"/"Folyamatban") - a fejléc korábban "Kész"
          // volt, amiből a szűrőben nem derült ki, mire lehet szűrni.
          header: "Állapot",
          render: (r) =>
            r.kesz ? <StatusBadge label="Kész" tone="success" /> : <StatusBadge label="Folyamatban" tone="neutral" />,
          // A kész projektek kerüljenek a lista végére rendezéskor.
          sortAccessor: (r) => (r.kesz ? 1 : 0),
        },
      ]}
    />
  );
}

/** Az ALAP nézet: a projektek fázisonként, egymás melletti oszlopokban -
 * egy pillantásra látszik, mi az, ami kész, mi az, ahol már csak utalni kell,
 * hol hiányzik a TIG, és hol még a szerződés sincs meg. */
export function UtokovetesTabla({ rows }: { rows: UtokovetesOverview[] }) {
  const oszlopok = FAZISOK.map((fazis) => ({
    ...fazis,
    projektek: rows.filter((r) => fazisa(r) === fazis.kulcs),
  }));

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      {oszlopok.map((oszlop) => (
        <div
          key={oszlop.kulcs}
          data-fazis={oszlop.kulcs}
          className="flex min-w-0 flex-col rounded-[var(--radius)] border border-border bg-surface-2"
        >
          <div className="border-b border-border px-3 py-2.5">
            <p className="flex items-baseline justify-between gap-2 text-[13px] font-medium text-text-primary">
              {oszlop.cim}
              <span className="tabular-nums text-text-muted">{oszlop.projektek.length}</span>
            </p>
            <p className="mt-0.5 text-[11.5px] text-text-muted">{oszlop.leiras}</p>
          </div>
          <div className="flex flex-col gap-2 p-3">
            {oszlop.projektek.length === 0 ? (
              <p className="py-2 text-[12.5px] text-text-muted">Nincs ilyen projekt.</p>
            ) : (
              oszlop.projektek.map((sor) => (
                <Link
                  key={sor.project_id}
                  href={`/utokovetes/${sor.project_id}`}
                  className="block rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 transition-colors hover:border-text-accent/40"
                >
                  <p className="truncate text-[13px] text-text-primary">{sor.project_nev ?? `#${sor.project_id}`}</p>
                  <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-[11.5px] text-text-muted">
                    {sor.projektkod && <span>{sor.projektkod}</span>}
                    <span>{formatDate(sor.forgatas_datuma)}</span>
                  </p>
                  <p
                    className={`mt-1 text-[12px] ${oszlop.kulcs === "kesz" ? "text-text-success" : "text-text-secondary"}`}
                  >
                    {hianyzik(sor)}
                  </p>
                </Link>
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
