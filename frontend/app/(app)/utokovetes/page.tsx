import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { formatDate, getUtokovetesOverview } from "@/lib/api";

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

/** Utókövetés - EGY oldalon mutatja minden diszpózott projekthez tartozó
 * eseti szerződés + teljesítési igazolás + forgatás utáni kérdőívválasz
 * állapotát, hogy ne kelljen projektenként külön-külön több oldalt
 * végignézni. A tényleges kezelés (mentés/generálás/küldés/kihagyás)
 * továbbra is a projekt oldalán vagy a saját (szerződés/TIG) oldalakon
 * történik - ez csak az áttekintés. */
export default async function UtokovetesPage() {
  const rows = await getUtokovetesOverview();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Utókövetés (${rows.length} diszpózott projekt)`}>
          <DataTable<(typeof rows)[number] & { id: number }>
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
                // Állapot-oszlop ("Kész"/"Folyamatban") - a fejléc korábban
                // "Kész" volt, amiből a szűrőben nem derült ki, mire lehet
                // szűrni.
                header: "Állapot",
                render: (r) =>
                  r.kesz ? (
                    <StatusBadge label="Kész" tone="success" />
                  ) : (
                    <StatusBadge label="Folyamatban" tone="neutral" />
                  ),
                // A kész projektek kerüljenek a lista végére rendezéskor.
                sortAccessor: (r) => (r.kesz ? 1 : 0),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
