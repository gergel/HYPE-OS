"use client";

import { useMemo, useState } from "react";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { authFetch } from "@/lib/authFetch";
import { DeliverableBoard, type BoardCard, type BoardColumn } from "@/components/deliverable/DeliverableBoard";
import type { Employee, FloraFeladat } from "@/lib/api";

// Nem a lib/api.ts-ből (next/headers-t behúzná egy kliens-komponensbe).
const FLORA_BASE_PATH = "/api/v1/flora";

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

export function FloraContent({
  feladatok,
  employees,
  statusOptions,
  canCreate,
  canDelete,
  canEdit,
}: {
  feladatok: FloraFeladat[];
  employees: Employee[];
  statusOptions: string[];
  canCreate: boolean;
  canDelete: boolean;
  canEdit: boolean;
}) {
  const [tab, setTab] = useState<"tabla" | "lista">("tabla");
  const [lista, setLista] = useState(feladatok);
  const employeeName = useMemo(() => new Map(employees.map((e) => [e.id, e.full_name])), [employees]);

  function toCard(f: FloraFeladat): BoardCard {
    const felelosNev = f.felelos_id ? employeeName.get(f.felelos_id) : null;
    return {
      id: f.id,
      href: `/flora/${f.id}`,
      title: f.megnevezes,
      subtitle: f.hatarido ? `Határidő: ${formatDate(f.hatarido)}` : null,
      badges: f.cimke ? [f.cimke] : [],
      mezok: felelosNev ? [{ cimke: "Felelős", ertek: felelosNev }] : [],
    };
  }

  const columns: BoardColumn[] = useMemo(() => {
    const byAllapot = new Map<string, FloraFeladat[]>();
    for (const f of lista) {
      const key = f.allapot && statusOptions.includes(f.allapot) ? f.allapot : "";
      if (!byAllapot.has(key)) byAllapot.set(key, []);
      byAllapot.get(key)!.push(f);
    }
    const oszlopok = statusOptions.map((s) => ({
      key: s,
      label: s,
      cards: (byAllapot.get(s) ?? []).map(toCard),
    }));
    const nincsAllapot = byAllapot.get("") ?? [];
    if (nincsAllapot.length > 0 || canEdit) {
      oszlopok.push({ key: "", label: "Nincs állapot", cards: nincsAllapot.map(toCard) });
    }
    return oszlopok;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lista, statusOptions, canEdit, employeeName]);

  async function allapotAtallitasa(feladatId: number, ujAllapot: string) {
    const eredeti = lista.find((f) => f.id === feladatId);
    if (!eredeti) return;
    const kovetkezo = ujAllapot === "" ? null : ujAllapot;
    if (eredeti.allapot === kovetkezo) return;
    setLista((elozo) => elozo.map((f) => (f.id === feladatId ? { ...f, allapot: kovetkezo } : f)));
    try {
      const res = await authFetch(`${FLORA_BASE_PATH}/${feladatId}`, {
        method: "PATCH",
        body: JSON.stringify({ allapot: kovetkezo }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setLista((elozo) => elozo.map((f) => (f.id === feladatId ? { ...f, allapot: eredeti.allapot } : f)));
        alert(`Az állapot módosítása nem sikerült: ${detail?.detail ?? res.status}`);
      }
    } catch (err) {
      setLista((elozo) => elozo.map((f) => (f.id === feladatId ? { ...f, allapot: eredeti.allapot } : f)));
      alert(`Az állapot módosítása nem sikerült (hálózati hiba): ${err}`);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setTab("tabla")}
          className={`rounded-[var(--radius)] px-3 py-1.5 text-[13px] ${
            tab === "tabla" ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:bg-surface-3"
          }`}
        >
          Tábla
        </button>
        <button
          type="button"
          onClick={() => setTab("lista")}
          className={`rounded-[var(--radius)] px-3 py-1.5 text-[13px] ${
            tab === "lista" ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:bg-surface-3"
          }`}
        >
          Lista
        </button>
      </div>
      <div className={tab === "tabla" ? "" : "hidden"}>
        <Card title={`FLÓRA (${lista.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={FLORA_BASE_PATH}
              addLabel="+ Új tétel hozzáadása"
              fields={[
                { name: "megnevezes", label: "Megnevezés", required: true },
                { name: "hatarido", label: "Határidő", type: "date" },
              ]}
            />
          )}
          <DeliverableBoard columns={columns} onAthelyezes={canEdit ? allapotAtallitasa : undefined} />
        </Card>
      </div>
      <div className={tab === "lista" ? "" : "hidden"}>
        <Card title={`FLÓRA (${lista.length})`}>
          <DataTable<FloraFeladat>
            rows={lista}
            emptyText="Még nincs felvett tétel."
            getHref={(f) => `/flora/${f.id}`}
            deleteHref={canDelete ? (f) => `${FLORA_BASE_PATH}/${f.id}` : undefined}
            filterable
            columns={[
              {
                header: "Megnevezés",
                render: (f) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${FLORA_BASE_PATH}/${f.id}`} field="megnevezes" value={f.megnevezes} />
                  ) : (
                    f.megnevezes
                  ),
                sortAccessor: (f) => f.megnevezes,
              },
              {
                header: "Címke",
                render: (f) => f.cimke ?? "–",
                sortAccessor: (f) => f.cimke,
              },
              {
                header: "Felelős",
                render: (f) => (f.felelos_id ? (employeeName.get(f.felelos_id) ?? "–") : "–"),
                sortAccessor: (f) => (f.felelos_id ? employeeName.get(f.felelos_id) : null),
              },
              {
                header: "Határidő",
                render: (f) => formatDate(f.hatarido),
                sortAccessor: (f) => f.hatarido,
              },
              {
                header: "Állapot",
                render: (f) => f.allapot ?? "–",
                sortAccessor: (f) => f.allapot,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
