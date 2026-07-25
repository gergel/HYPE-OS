"use client";

import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { DeliverableBoard, type BoardCard, type BoardColumn } from "@/components/deliverable/DeliverableBoard";
import { ForgatasokCalendar } from "@/components/deliverable/ForgatasokCalendar";
import { UtomunkaViewTabs } from "@/components/deliverable/UtomunkaViewTabs";
import type { Deliverable, Employee } from "@/lib/api";

// Nem importáljuk az ENTITY_PATHS-t a lib/api.ts-ből (bár csak egy sima
// konstans) - az a modul a `next/headers`-t is importálja (szerver-oldali
// cookie-olvasáshoz), és egy kliens komponensbe akár csak egyetlen NEM
// type-only importja is beviszi a teljes modult a kliens bundle-be, ami
// build hibát okoz ("next/headers" csak Server Component-ekben érhető el).
const DELIVERABLE_BASE_PATH = "/api/v1/deliverables";

const NO_STATUS_KEY = "__nincs_allapot__";

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

type CalendarProject = { id: number; nev: string; forgatas_datuma: string | null; forgatas_datuma_vege: string | null };

/** Az Utómunka oldal tényleges tartalma (tábla + naptár + admin lista) - a
 * kezdeti szerver-oldali renderelés csak a legutóbb módosított anyagok/
 * forgatások egy szeletét kapja meg (lásd app/utomunka/page.tsx), hogy az
 * oldal azonnal betöltődjön még nagyon sok, rég lezárt/nem használt rekord
 * mellett is - a maradékot ez a komponens tölti be a háttérben,
 * betöltés-jelző/blokkolás nélkül, és csendben beleolvasztja a listába. */
export function UtomunkaContent({
  initialDeliverables,
  deliverablesHasMore,
  initialProjects,
  projectsHasMore,
  employees,
  statusOptions,
  vinyoOptions,
  canCreate,
  canDelete,
  canEdit,
}: {
  initialDeliverables: Deliverable[];
  deliverablesHasMore: boolean;
  initialProjects: CalendarProject[];
  projectsHasMore: boolean;
  employees: Employee[];
  statusOptions: string[];
  vinyoOptions: string[];
  canCreate: boolean;
  canDelete: boolean;
  canEdit: boolean;
}) {
  const [deliverables, setDeliverables] = useState(initialDeliverables);
  const [projects, setProjects] = useState(initialProjects);

  useEffect(() => {
    if (!deliverablesHasMore) return;
    authFetch(`/api/v1/deliverables?skip=${initialDeliverables.length}&limit=5000`)
      .then((res) => (res.ok ? res.json() : []))
      .then((rest: Deliverable[]) => setDeliverables((prev) => [...prev, ...rest]))
      .catch(() => {});
    // csak első betöltéskor fusson - a szűrő/rendezés kliens-oldali állapota nem függ ettől
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!projectsHasMore) return;
    authFetch(`/api/v1/projects?skip=${initialProjects.length}&limit=5000`)
      .then((res) => (res.ok ? res.json() : []))
      .then((rest: CalendarProject[]) => setProjects((prev) => [...prev, ...rest]))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const employeeName = useMemo(() => new Map(employees.map((e) => [e.id, e.full_name])), [employees]);

  function toCard(d: Deliverable, badges: string[]): BoardCard {
    const subtitleParts = [
      d.hatarido ? `Határidő: ${formatDate(d.hatarido)}` : null,
      d.assigned_to_employee_id ? `Kiosztva: ${employeeName.get(d.assigned_to_employee_id) ?? "?"}` : null,
    ].filter((p): p is string => p !== null);
    return {
      id: d.id,
      href: `/utomunka/${d.id}`,
      title: d.projekt_neve,
      subtitle: subtitleParts.length > 0 ? subtitleParts.join(" · ") : null,
      badges,
    };
  }

  const statusColumns: BoardColumn[] = useMemo(() => {
    const byStatus = new Map<string, Deliverable[]>();
    for (const d of deliverables) {
      const key = d.allapot && statusOptions.includes(d.allapot) ? d.allapot : NO_STATUS_KEY;
      if (!byStatus.has(key)) byStatus.set(key, []);
      byStatus.get(key)!.push(d);
    }
    return [
      ...statusOptions.map((s) => ({
        key: s,
        label: s,
        cards: (byStatus.get(s) ?? []).map((d) => toCard(d, d.vinyok ?? [])),
      })),
      ...(byStatus.has(NO_STATUS_KEY)
        ? [{ key: NO_STATUS_KEY, label: "Nincs állapot", cards: byStatus.get(NO_STATUS_KEY)!.map((d) => toCard(d, d.vinyok ?? [])) }]
        : []),
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deliverables, statusOptions, employeeName]);

  const vinyoColumns: BoardColumn[] = useMemo(() => {
    const byVinyo = new Map<string, Deliverable[]>();
    for (const d of deliverables) {
      for (const v of d.vinyok ?? []) {
        if (!byVinyo.has(v)) byVinyo.set(v, []);
        byVinyo.get(v)!.push(d);
      }
    }
    return vinyoOptions
      .filter((v) => (byVinyo.get(v)?.length ?? 0) > 0)
      .map((v) => ({ key: v, label: v, cards: byVinyo.get(v)!.map((d) => toCard(d, d.allapot ? [d.allapot] : [])) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deliverables, vinyoOptions, employeeName]);

  const calendarProjects = useMemo(() => projects.filter((p) => p.forgatas_datuma !== null), [projects]);

  return (
    <UtomunkaViewTabs
      board={
        <div className="space-y-6">
          <Card title="Állapot szerint">
            <DeliverableBoard columns={statusColumns} />
          </Card>
          <Card title="Forgatások naptár">
            <ForgatasokCalendar projects={calendarProjects} />
          </Card>
          <Card title="Vinyók szerint">
            <DeliverableBoard columns={vinyoColumns} />
          </Card>
        </div>
      }
      list={
        <Card title={`Utómunka (${deliverables.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={DELIVERABLE_BASE_PATH}
              addLabel="+ Új anyag hozzáadása"
              fields={[
                { name: "projekt_neve", label: "Anyag neve", required: true },
                { name: "hatarido", label: "Határidő", type: "date" },
              ]}
            />
          )}
          <DataTable<Deliverable>
            rows={deliverables}
            emptyText="Még nincs felvett vágandó anyag - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(d) => `/utomunka/${d.id}`}
            deleteHref={canDelete ? (d) => `${DELIVERABLE_BASE_PATH}/${d.id}` : undefined}
            filterable
            columns={[
              {
                header: "Anyag",
                render: (d) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${DELIVERABLE_BASE_PATH}/${d.id}`} field="projekt_neve" value={d.projekt_neve} />
                  ) : (
                    d.projekt_neve
                  ),
                sortAccessor: (d) => d.projekt_neve,
              },
              {
                header: "Állapot",
                render: (d) => (
                  <EditableStatusBadge
                    patchPath={`${DELIVERABLE_BASE_PATH}/${d.id}`}
                    field="allapot"
                    value={d.allapot}
                    options={statusOptions}
                  />
                ),
                sortAccessor: (d) => d.allapot,
              },
              {
                header: "Határidő",
                render: (d) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${DELIVERABLE_BASE_PATH}/${d.id}`} field="hatarido" value={d.hatarido} type="date" />
                  ) : (
                    formatDate(d.hatarido)
                  ),
                sortAccessor: (d) => d.hatarido,
              },
              {
                header: "Kiküldve",
                align: "right",
                render: (d) => (
                  <StatusBadge
                    label={d.anyag_kikuldve ? "Kiküldve" : "Nincs kiküldve"}
                    tone={d.anyag_kikuldve ? "success" : "warning"}
                  />
                ),
                sortAccessor: (d) => (d.anyag_kikuldve ? 1 : 0),
              },
            ]}
          />
        </Card>
      }
    />
  );
}
