"use client";

import { useState } from "react";
import { SearchableIdPicker } from "@/components/SearchableIdPicker";
import { authFetch } from "@/lib/authFetch";
import type { Employee } from "@/lib/api";

/** Kik kapják MÁSOLATBAN (CC) az ÖSSZES kimenő diszpót - az előzetest és a
 * teljeset is. A Beállítások oldalon, adminként szerkeszthető névsor; a
 * leveleken a HYPE_CC env fix címei MELLÉ kerülnek (lásd backend
 * services/dispo.masolat_cimzettek). Minden változtatás azonnal ment - ugyanaz
 * a minta, mint a Diszpó felelősöknél (DispoResponsiblesManager). */
export function DiszpoMasolatManager({
  initial,
  employees,
}: {
  initial: number[];
  employees: Employee[];
}) {
  const [ids, setIds] = useState<number[]>(initial);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const employeeById = new Map(employees.map((e) => [e.id, e]));

  async function save(next: number[]) {
    setIds(next);
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const res = await authFetch("/api/v1/dispo-responsibles/masolat", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ employee_ids: next }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setError(detail?.detail ?? `HTTP ${res.status}`);
        return;
      }
      setSaved(true);
    } catch (err) {
      setError(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {ids.length === 0 && <p className="text-[13px] text-text-muted">Nincs beállítva másolat-címzett.</p>}
        {ids.map((id) => {
          const ember = employeeById.get(id);
          return (
            <span
              key={id}
              className="flex items-center gap-1.5 rounded-[var(--radius)] bg-surface-3 px-2.5 py-1 text-[13px] text-text-primary"
            >
              {ember?.full_name ?? `#${id}`}
              {/* Cím nélkül a levél nem tud hova menni - jelezzük, ne csak
                  csendben maradjon le. */}
              {ember && !ember.email && <span className="text-[11.5px] text-text-danger">(nincs email!)</span>}
              <button
                type="button"
                disabled={busy}
                onClick={() => save(ids.filter((x) => x !== id))}
                className="text-text-muted transition-colors hover:text-text-danger disabled:opacity-50"
                title="Eltávolítás"
              >
                ✕
              </button>
            </span>
          );
        })}
      </div>

      <SearchableIdPicker
        value={null}
        options={employees
          .filter((e) => !ids.includes(e.id))
          .map((e) => ({ id: e.id, label: e.full_name, sublabel: e.email, group: e.tipus }))}
        onChange={(next) => {
          if (next !== null) save([...ids, next]);
        }}
        placeholder="Másolat-címzett hozzáadása…"
        disabled={busy}
        className="min-w-[240px]"
      />

      {error && <p className="text-[12px] text-text-danger">{error}</p>}
      {saved && !error && <p className="text-[12px] text-text-success">Mentve.</p>}
    </div>
  );
}
