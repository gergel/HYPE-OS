"use client";

import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import type { UtokovetesOverviewProjectCode } from "@/lib/api";

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

/** Azok a projektkódok, amiken FORGATÁS NÉLKÜL van alvállalkozói papírozás -
 * lásd backend utokovetes_admin.py "projektkód-szintű ág". Külön kis lista a
 * fő UtokovetesLista mellett, mert a sorok alakja más (nincs forgatási dátum,
 * aláírás-várás, kifizetés-számláló - lásd UtokovetesOverviewProjectCode), és
 * a projektkódnak nincs saját Utókövetés-adatlapja: a teendő magán a Project
 * Code oldalon (projektek/project-kodok/[id]) van, ezért oda navigál a sor. */
export function UtokovetesProjektkodLista({ rows }: { rows: UtokovetesOverviewProjectCode[] }) {
  return (
    <DataTable<UtokovetesOverviewProjectCode & { id: number }>
      filterable
      rows={rows.map((r) => ({ ...r, id: r.project_code_id }))}
      emptyText="Nincs ilyen projektkód."
      getHref={(r) => `/projektek/project-kodok/${r.project_code_id}`}
      columns={[
        { header: "Projekt", render: (r) => r.project_nev ?? `#${r.project_code_id}`, sortAccessor: (r) => r.project_nev },
        { header: "Projektkód", render: (r) => r.projektkod ?? "–", sortAccessor: (r) => r.projektkod },
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
          header: "Állapot",
          render: (r) =>
            r.kesz ? <StatusBadge label="Kész" tone="success" /> : <StatusBadge label="Folyamatban" tone="neutral" />,
          sortAccessor: (r) => (r.kesz ? 1 : 0),
        },
      ]}
    />
  );
}
