"use client";

import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { ForgatasokCalendar } from "@/components/deliverable/ForgatasokCalendar";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { ProjectDetailModal } from "@/components/ProjectDetailModal";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { authFetch } from "@/lib/authFetch";
import { useLiveTopic } from "@/lib/live";
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
 * háttérben, betöltés-jelző/blokkolás nélkül.
 *
 * A szűrés (szabadszavas keresőmező) itt, szülő szinten fut, NEM a DataTable
 * saját beépített szűrőjével - így ugyanaz a szűrés a táblázat ÉS a naptár
 * nézetre is érvényes marad, akármelyiket nézi épp a felhasználó. A
 * projektkód (ami csak egy lookup-olt szöveg, nem tényleges Project mező) is
 * bekerül a keresett szövegbe, hogy arra is lehessen szűrni. */
export function ProjektekContent({
  initialProjects,
  hasMore,
  projectCodes,
  statusOptions,
  canCreate,
  canDelete,
  canEdit,
}: {
  initialProjects: Project[];
  hasMore: boolean;
  projectCodes: ProjectCode[];
  statusOptions: string[];
  canCreate: boolean;
  canDelete: boolean;
  canEdit: boolean;
}) {
  const [projects, setProjects] = useState(initialProjects);
  const [view, setView] = useState<"table" | "calendar">("table");
  const [query, setQuery] = useState("");
  const [modalProjectId, setModalProjectId] = useState<number | null>(null);

  useEffect(() => {
    if (!hasMore) return;
    authFetch(`/api/v1/projects?skip=${initialProjects.length}&limit=5000`)
      .then((res) => (res.ok ? res.json() : []))
      .then((rest: Project[]) => setProjects((prev) => [...prev, ...rest]))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A lista a komponens saját állapotában él (a szerver csak az első szeletet
  // adja), ezért a háttérfrissítésnél itt kell újratölteni - pl. amikor a
  // naptár-szinkron új forgatást hoz be.
  useLiveTopic("projects", () => {
    authFetch(`/api/v1/projects?limit=5000`)
      .then((res) => (res.ok ? res.json() : null))
      .then((fresh: Project[] | null) => fresh && setProjects(fresh))
      .catch(() => {});
  });

  const projectCodeById = new Map(projectCodes.map((pc) => [pc.id, pc.projektkod]));

  const filteredProjects = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return projects;
    return projects.filter((p) => {
      const code = projectCodeById.get(p.project_code_id) ?? "";
      const haystack = `${JSON.stringify(p)} ${code}`.toLowerCase();
      return haystack.includes(needle);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projects, query, projectCodes]);

  return (
    <Card title={`Projektek (${filteredProjects.length}${filteredProjects.length !== projects.length ? ` / ${projects.length}` : ""})`}>
      {canCreate && (
        <QuickCreateForm
          postPath={PROJECT_BASE_PATH}
          addLabel="+ Új projekt hozzáadása"
          fields={[
            { name: "nev", label: "Név", required: true },
            { name: "project_code_id", label: "Project Code", type: "select", required: true, options: projectCodes.map((pc) => ({ value: pc.id, label: pc.projektkod })) },
            { name: "forgatas_datuma", label: "Forgatás dátuma", type: "date" },
            { name: "helyszin", label: "Helyszín" },
          ]}
        />
      )}

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Szűrés bármelyik oszlopra…"
          className="w-full max-w-xs rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none"
        />
        <div className="flex items-center gap-1 rounded-[var(--radius)] border border-border p-0.5">
          <button
            type="button"
            onClick={() => setView("table")}
            className={`rounded-[calc(var(--radius)-2px)] px-2.5 py-1 text-[12px] ${
              view === "table" ? "bg-bg-accent text-text-accent" : "text-text-secondary hover:bg-surface-3"
            }`}
          >
            Táblázat
          </button>
          <button
            type="button"
            onClick={() => setView("calendar")}
            className={`rounded-[calc(var(--radius)-2px)] px-2.5 py-1 text-[12px] ${
              view === "calendar" ? "bg-bg-accent text-text-accent" : "text-text-secondary hover:bg-surface-3"
            }`}
          >
            Naptár
          </button>
        </div>
      </div>

      {view === "table" ? (
        <DataTable<Project>
          rows={filteredProjects}
          emptyText={query ? "Nincs találat a szűrésre." : "Még nincs felvett projekt - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."}
          deleteHref={canDelete ? (p) => `${PROJECT_BASE_PATH}/${p.id}` : undefined}
          onRowClick={(id) => setModalProjectId(id)}
          columns={[
            {
              header: "Név",
              render: (p) =>
                canEdit ? <EditableTableCell patchPath={`${PROJECT_BASE_PATH}/${p.id}`} field="nev" value={p.nev} /> : p.nev,
              sortAccessor: (p) => p.nev,
            },
            {
              header: "Projektkód",
              render: (p) => projectCodeById.get(p.project_code_id) ?? "–",
              sortAccessor: (p) => projectCodeById.get(p.project_code_id),
            },
            {
              header: "Forgatás dátuma",
              render: (p) =>
                canEdit ? (
                  <EditableTableCell patchPath={`${PROJECT_BASE_PATH}/${p.id}`} field="forgatas_datuma" value={p.forgatas_datuma} type="date" />
                ) : (
                  formatDate(p.forgatas_datuma)
                ),
              sortAccessor: (p) => p.forgatas_datuma,
            },
            {
              header: "Helyszín",
              render: (p) =>
                canEdit ? (
                  <EditableTableCell patchPath={`${PROJECT_BASE_PATH}/${p.id}`} field="helyszin" value={p.helyszin} />
                ) : (
                  p.helyszin ?? "–"
                ),
              sortAccessor: (p) => p.helyszin,
            },
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
      ) : (
        <ForgatasokCalendar projects={filteredProjects} onProjectClick={(id) => setModalProjectId(id)} />
      )}

      <ProjectDetailModal projectId={modalProjectId} onClose={() => setModalProjectId(null)} />
    </Card>
  );
}
