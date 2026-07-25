"use client";

import { useMemo, useState } from "react";
import { ActionButton } from "@/components/ActionButton";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { ForgatasokCalendar } from "@/components/deliverable/ForgatasokCalendar";
import { ProjectDetailModal } from "@/components/ProjectDetailModal";
import { StatusBadge } from "@/components/StatusBadge";
import type { Project, ProjectCode } from "@/lib/api";

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

/** A Naptár/Diszpó oldal tényleges tartalma - a Project rekordokon
 * ténylegesen tárolt diszpó-állapotot (diszpo/elozetes_diszpo_kuldes,
 * lásd backend/app/services/dispo.py) mutatja meg táblázat/naptár nézetben,
 * a két meglévő küldés-végpontra (POST .../diszpo/elozetes, .../diszpo/kuldes)
 * mutató gombokkal - ugyanazok az akciók, amik eddig csak a Projekt
 * részletnézet "Diszpó küldése" fülén voltak elérhetők, itt viszont egy
 * helyen, az ÖSSZES forgatásra rálátva, hogy ne kelljen projektenként
 * külön-külön benyitni csak azért, hogy admin lássa, kinek van még hátra a
 * diszpója. Csak azok a projektek jelennek meg, amiknek van forgatás
 * dátuma - diszpó csak ezekhez értelmezhető. */
export function NaptarDiszpoContent({
  projects,
  projectCodes,
  canSend,
}: {
  projects: Project[];
  projectCodes: ProjectCode[];
  canSend: boolean;
}) {
  const [view, setView] = useState<"table" | "calendar">("table");
  const [query, setQuery] = useState("");
  const [modalProjectId, setModalProjectId] = useState<number | null>(null);

  const projectCodeById = new Map(projectCodes.map((pc) => [pc.id, pc.projektkod]));

  const scheduled = useMemo(() => projects.filter((p) => p.forgatas_datuma !== null), [projects]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return scheduled;
    return scheduled.filter((p) => {
      const code = projectCodeById.get(p.project_code_id) ?? "";
      const haystack = `${JSON.stringify(p)} ${code}`.toLowerCase();
      return haystack.includes(needle);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scheduled, query, projectCodes]);

  const elozetesKuldve = filtered.filter((p) => p.elozetes_diszpo_kuldes).length;
  const teljesKuldve = filtered.filter((p) => p.diszpo).length;

  return (
    <Card title={`Naptár / Diszpó (${filtered.length} forgatás)`}>
      <p className="mb-3 text-[13px] text-text-secondary">
        {elozetesKuldve} előzetes diszpó elküldve · {teljesKuldve} teljes diszpó kiküldve · {filtered.length - teljesKuldve} még hátra van
      </p>

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
          rows={filtered}
          emptyText={query ? "Nincs találat a szűrésre." : "Nincs dátummal rendelkező forgatás."}
          onRowClick={(id) => setModalProjectId(id)}
          columns={[
            {
              header: "Név",
              render: (p) => p.nev,
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
                p.forgatas_datuma_vege && p.forgatas_datuma_vege !== p.forgatas_datuma
                  ? `${formatDate(p.forgatas_datuma)} – ${formatDate(p.forgatas_datuma_vege)}`
                  : formatDate(p.forgatas_datuma),
              sortAccessor: (p) => p.forgatas_datuma,
            },
            {
              header: "Helyszín",
              render: (p) => p.helyszin ?? "–",
              sortAccessor: (p) => p.helyszin,
            },
            {
              header: "Előzetes diszpó",
              render: (p) => (
                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  {p.elozetes_diszpo_kuldes ? (
                    <StatusBadge label={p.elozetes_diszpo_kuldes} tone="teal" />
                  ) : (
                    <StatusBadge label="Nincs elküldve" tone="neutral" />
                  )}
                  {canSend && (
                    <ActionButton
                      path={`/api/v1/projects/${p.id}/diszpo/elozetes`}
                      label="Küldés"
                      confirmMessage="Elküldi az előzetes diszpót a résztvevőknek. Folytatod?"
                    />
                  )}
                </div>
              ),
            },
            {
              header: "Diszpó",
              render: (p) => (
                <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  {p.diszpo ? <StatusBadge label={p.diszpo} tone="success" /> : <StatusBadge label="Nincs kiküldve" tone="neutral" />}
                  {canSend && (
                    <ActionButton
                      path={`/api/v1/projects/${p.id}/diszpo/kuldes`}
                      label="Küldés"
                      confirmMessage="Elküldi a teljes diszpót (technika listával, PDF-fel) a résztvevőknek. Folytatod?"
                    />
                  )}
                </div>
              ),
            },
          ]}
        />
      ) : (
        <ForgatasokCalendar projects={filtered} onProjectClick={(id) => setModalProjectId(id)} />
      )}

      <ProjectDetailModal projectId={modalProjectId} projectCodes={projectCodes} onClose={() => setModalProjectId(null)} />
    </Card>
  );
}
