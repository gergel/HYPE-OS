"use client";

import { useMemo } from "react";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { DeliverableBoard, type BoardCard, type BoardColumn } from "@/components/deliverable/DeliverableBoard";
import { ForgatasokCalendar } from "@/components/deliverable/ForgatasokCalendar";
import type { AgiTodoItem, AllapotBeallitas, Deliverable, Project } from "@/lib/api";

// Nem a lib/api.ts-ből (next/headers-t behúzná egy kliens-komponensbe).
const AGI_TODO_BASE_PATH = "/api/v1/agi-todo";

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

/** Az Ági oldal - saját To-Do lista + a MEGLÉVŐ, élő Utómunka tábla és
 * Forgatások naptár beágyazva (nem külön Notion-import-másolat - lásd a
 * felhasználóval egyeztetett döntést). A beágyazott két nézet szándékosan
 * EGYSZERŰSÍTETT/csak-olvasható: a teljes, szerkeszthető, húzható verzió
 * a /utomunka és /naptar oldalakon él, ide csak az áttekintés kell. */
export function AgiContent({
  items,
  statusOptions,
  canCreate,
  canDelete,
  canEdit,
  deliverables,
  deliverableStatusOptions,
  allapotBeallitasok,
  projects,
}: {
  items: AgiTodoItem[];
  statusOptions: string[];
  canCreate: boolean;
  canDelete: boolean;
  canEdit: boolean;
  deliverables: Deliverable[];
  deliverableStatusOptions: string[];
  allapotBeallitasok: AllapotBeallitas[];
  projects: Project[];
}) {
  const deliverableColumns: BoardColumn[] = useMemo(() => {
    const byStatus = new Map<string, Deliverable[]>();
    for (const d of deliverables) {
      const key = d.allapot && deliverableStatusOptions.includes(d.allapot) ? d.allapot : "";
      if (!byStatus.has(key)) byStatus.set(key, []);
      byStatus.get(key)!.push(d);
    }
    const szinek = new Map(allapotBeallitasok.map((b) => [b.allapot, b.szin]));
    const helye = new Map(allapotBeallitasok.map((b, i) => [b.allapot, i]));
    const rendezett = [...deliverableStatusOptions].sort(
      (a, b) => (helye.get(a) ?? Number.MAX_SAFE_INTEGER) - (helye.get(b) ?? Number.MAX_SAFE_INTEGER),
    );
    return rendezett
      .map((s) => ({
        key: s,
        label: s,
        szin: szinek.get(s) ?? null,
        cards: (byStatus.get(s) ?? []).map(
          (d): BoardCard => ({
            id: d.id,
            href: `/utomunka/${d.id}`,
            title: d.projekt_neve,
            subtitle: d.hatarido ? `Határidő: ${formatDate(d.hatarido)}` : null,
            badges: [],
          }),
        ),
      }))
      .filter((col) => col.cards.length > 0);
  }, [deliverables, deliverableStatusOptions, allapotBeallitasok]);

  const calendarProjects = useMemo(() => projects.filter((p) => p.forgatas_datuma !== null), [projects]);

  return (
    <div className="space-y-6">
      <Card title={`ÁGI - To-Do List (${items.length})`}>
        {canCreate && (
          <QuickCreateForm
            postPath={AGI_TODO_BASE_PATH}
            addLabel="+ Új feladat hozzáadása"
            fields={[
              { name: "feladat", label: "Feladat", required: true },
              { name: "hatarido", label: "Határidő", type: "date" },
            ]}
          />
        )}
        <DataTable<AgiTodoItem>
          rows={items}
          emptyText="Még nincs felvett feladat."
          getHref={(t) => `/agi/${t.id}`}
          deleteHref={canDelete ? (t) => `${AGI_TODO_BASE_PATH}/${t.id}` : undefined}
          filterable
          columns={[
            {
              header: "Feladat",
              render: (t) =>
                canEdit ? (
                  <EditableTableCell patchPath={`${AGI_TODO_BASE_PATH}/${t.id}`} field="feladat" value={t.feladat} />
                ) : (
                  t.feladat
                ),
              sortAccessor: (t) => t.feladat,
            },
            {
              header: "Ügyfél",
              render: (t) =>
                canEdit ? (
                  <EditableTableCell patchPath={`${AGI_TODO_BASE_PATH}/${t.id}`} field="ugyfel" value={t.ugyfel} />
                ) : (
                  t.ugyfel ?? "–"
                ),
              sortAccessor: (t) => t.ugyfel,
            },
            {
              header: "Határidő",
              render: (t) =>
                canEdit ? (
                  <EditableTableCell patchPath={`${AGI_TODO_BASE_PATH}/${t.id}`} field="hatarido" value={t.hatarido} type="date" />
                ) : (
                  formatDate(t.hatarido)
                ),
              sortAccessor: (t) => t.hatarido,
            },
            {
              header: "Állapot",
              render: (t) => (
                <EditableStatusBadge
                  patchPath={`${AGI_TODO_BASE_PATH}/${t.id}`}
                  field="allapot"
                  value={t.allapot}
                  options={statusOptions}
                />
              ),
              sortAccessor: (t) => t.allapot,
            },
          ]}
        />
      </Card>

      <Card title="Utómunka (áttekintés)">
        <DeliverableBoard columns={deliverableColumns} />
      </Card>

      <Card title="Forgatások">
        <ForgatasokCalendar projects={calendarProjects} />
      </Card>
    </div>
  );
}
