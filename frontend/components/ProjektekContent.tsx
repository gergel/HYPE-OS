"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { authFetch } from "@/lib/authFetch";
import type { Project, ProjectCode } from "@/lib/api";

// Nem importáljuk az ENTITY_PATHS-t a lib/api.ts-ből (bár csak egy sima
// konstans) - az a modul a `next/headers`-t is importálja (szerver-oldali
// cookie-olvasáshoz), és egy kliens komponensbe akár csak egyetlen NEM
// type-only importja is beviszi a teljes modult a kliens bundle-be, ami
// build hibát okoz ("next/headers" csak Server Component-ekben érhető el).
const PROJECT_BASE_PATH = "/api/v1/projects";

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

/** A Projektek oldal tényleges tartalma - a kezdeti szerver-oldali
 * renderelés csak a legutóbb módosított projektek egy szeletét kapja meg
 * (lásd app/projektek/page.tsx), hogy az oldal azonnal betöltődjön még sok,
 * rég lezárt projekt mellett is - a maradékot ez a komponens tölti be a
 * háttérben, betöltés-jelző/blokkolás nélkül. */
export function ProjektekContent({
  initialProjects,
  hasMore,
  projectCodes,
  statusOptions,
}: {
  initialProjects: Project[];
  hasMore: boolean;
  projectCodes: ProjectCode[];
  statusOptions: string[];
}) {
  const [projects, setProjects] = useState(initialProjects);

  useEffect(() => {
    if (!hasMore) return;
    authFetch(`/api/v1/projects?skip=${initialProjects.length}&limit=5000`)
      .then((res) => (res.ok ? res.json() : []))
      .then((rest: Project[]) => setProjects((prev) => [...prev, ...rest]))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const projectCodeById = new Map(projectCodes.map((pc) => [pc.id, pc.projektkod]));

  return (
    <Card title={`Projektek (${projects.length})`}>
      <DataTable<Project>
        rows={projects}
        emptyText="Még nincs felvett projekt - importáld a Notionból, vagy adj hozzá egyet a /api/v1/projects végponton."
        getHref={(p) => `/projektek/${p.id}`}
        deleteHref={(p) => `${PROJECT_BASE_PATH}/${p.id}`}
        filterable
        columns={[
          { header: "Név", render: (p) => p.nev, sortAccessor: (p) => p.nev },
          {
            header: "Projektkód",
            render: (p) => projectCodeById.get(p.project_code_id) ?? "–",
            sortAccessor: (p) => projectCodeById.get(p.project_code_id),
          },
          { header: "Forgatás dátuma", render: (p) => formatDate(p.forgatas_datuma), sortAccessor: (p) => p.forgatas_datuma },
          { header: "Helyszín", render: (p) => p.helyszin ?? "–", sortAccessor: (p) => p.helyszin },
          {
            header: "Állapot",
            render: (p) => (
              <EditableStatusBadge
                patchPath={`${PROJECT_BASE_PATH}/${p.id}`}
                field="allapot"
                value={p.allapot}
                options={statusOptions}
              />
            ),
            sortAccessor: (p) => p.allapot,
          },
        ]}
      />
    </Card>
  );
}
