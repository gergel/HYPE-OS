"use client";

import { useMemo, useState } from "react";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import type { Employee, HypeTodoItem } from "@/lib/api";

// Nem a lib/api.ts-ből importáljuk ezeket (bár csak sima konstansok/
// függvények) - az a modul a next/headers-t is behúzza (szerver-oldali
// cookie-olvasáshoz), és egy kliens-komponensbe akár csak egyetlen NEM
// type-only importja is beviszi a teljes modult, ami build hibát okoz.
const HYPE_TODO_BASE_PATH = "/api/v1/hype-todo";

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

const KESZ_ALLAPOT = "Done";

export function HypeTodoContent({
  items,
  employees,
  statusOptions,
  kategoriaOptions,
  canCreate,
  canDelete,
  canEdit,
}: {
  items: HypeTodoItem[];
  employees: Employee[];
  statusOptions: string[];
  kategoriaOptions: string[];
  canCreate: boolean;
  canDelete: boolean;
  canEdit: boolean;
}) {
  const [tab, setTab] = useState<"nyitott" | "kesz">("nyitott");
  const employeeName = useMemo(() => new Map(employees.map((e) => [e.id, e.full_name])), [employees]);

  const nyitottak = items.filter((i) => i.allapot !== KESZ_ALLAPOT);
  const keszek = items.filter((i) => i.allapot === KESZ_ALLAPOT);
  const lista = tab === "nyitott" ? nyitottak : keszek;

  function felelosNevek(item: HypeTodoItem): string {
    const nevek = item.felelos_employee_ids.map((id) => employeeName.get(id)).filter((n): n is string => !!n);
    return nevek.length > 0 ? nevek.join(", ") : "–";
  }

  return (
    <Card title={`HYPE TO-DO LIST (${items.length})`}>
      {canCreate && (
        <QuickCreateForm
          postPath={HYPE_TODO_BASE_PATH}
          addLabel="+ Új feladat hozzáadása"
          fields={[
            { name: "feladat", label: "Feladat", required: true },
            { name: "hatarido", label: "Határidő", type: "date" },
          ]}
        />
      )}
      <div className="mb-4 flex gap-2">
        <button
          type="button"
          onClick={() => setTab("nyitott")}
          className={`rounded-[var(--radius)] px-3 py-1.5 text-[13px] ${
            tab === "nyitott" ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:bg-surface-3"
          }`}
        >
          Feladatok ({nyitottak.length})
        </button>
        <button
          type="button"
          onClick={() => setTab("kesz")}
          className={`rounded-[var(--radius)] px-3 py-1.5 text-[13px] ${
            tab === "kesz" ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:bg-surface-3"
          }`}
        >
          Kész feladatok ({keszek.length})
        </button>
      </div>
      <DataTable<HypeTodoItem>
        rows={lista}
        emptyText="Még nincs felvett feladat."
        getHref={(t) => `/hype-todo-lista/${t.id}`}
        deleteHref={canDelete ? (t) => `${HYPE_TODO_BASE_PATH}/${t.id}` : undefined}
        filterable
        columns={[
          {
            header: "Feladat",
            render: (t) =>
              canEdit ? (
                <EditableTableCell patchPath={`${HYPE_TODO_BASE_PATH}/${t.id}`} field="feladat" value={t.feladat} />
              ) : (
                t.feladat
              ),
            sortAccessor: (t) => t.feladat,
          },
          {
            header: "Kategória",
            render: (t) =>
              canEdit ? (
                <EditableStatusBadge
                  patchPath={`${HYPE_TODO_BASE_PATH}/${t.id}`}
                  field="kategoria"
                  value={t.kategoria}
                  options={kategoriaOptions}
                  placeholder="Nincs kategória"
                />
              ) : (
                t.kategoria ?? "–"
              ),
            sortAccessor: (t) => t.kategoria,
          },
          {
            header: "Felelős",
            render: felelosNevek,
            sortAccessor: felelosNevek,
          },
          {
            header: "Határidő",
            render: (t) =>
              canEdit ? (
                <EditableTableCell patchPath={`${HYPE_TODO_BASE_PATH}/${t.id}`} field="hatarido" value={t.hatarido} type="date" />
              ) : (
                formatDate(t.hatarido)
              ),
            sortAccessor: (t) => t.hatarido,
          },
          {
            header: "Állapot",
            render: (t) => (
              <EditableStatusBadge
                patchPath={`${HYPE_TODO_BASE_PATH}/${t.id}`}
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
  );
}
