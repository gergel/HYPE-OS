"use client";

import { useState } from "react";
import { SearchableIdPicker } from "@/components/SearchableIdPicker";
import { authFetch } from "@/lib/authFetch";
import type { DispoResponsibles, Employee } from "@/lib/api";

const SIDES = [
  {
    key: "gyartas" as const,
    label: "Gyártás",
    hint: "A teendő akkor kerül le, ha az előzetes diszpó kiment - vagy ha a teljes diszpó ment ki előzetes nélkül.",
  },
  {
    key: "technika" as const,
    label: "Technika",
    hint: "A teendő kizárólag a teljes diszpó kiküldésével kerül le (az előzetes önmagában nem elég).",
  },
];

/** Diszpó-felelősök beállítása oldalanként. A beállított emberek "Teendőim"
 * widgetjében minden nap megjelennek a MÁSNAPI forgatások diszpói, amíg a saját
 * oldaluk szerinti küldés meg nem történt (lásd backend
 * models/dispo_responsible.py, api/routes/dashboard.py).
 *
 * Ugyanaz az ember mindkét oldalon szerepelhet - ilyenkor két külön teendőt
 * lát ugyanarra a forgatásra, mert a kettő más-más feltétellel kerül le. */
export function DispoResponsiblesManager({
  initial,
  employees,
}: {
  initial: DispoResponsibles;
  employees: Employee[];
}) {
  const [value, setValue] = useState<DispoResponsibles>(initial);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const employeeById = new Map(employees.map((e) => [e.id, e]));

  async function save(next: DispoResponsibles) {
    setValue(next);
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const res = await authFetch("/api/v1/dispo-responsibles", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(next),
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
    <div className="space-y-5">
      {SIDES.map((side) => {
        const ids = value[side.key];
        const available = employees.filter((e) => !ids.includes(e.id));
        return (
          <div key={side.key}>
            <p className="text-[13px] font-medium text-text-primary">{side.label}</p>
            <p className="mb-2 text-[12px] text-text-muted">{side.hint}</p>

            <div className="mb-2 flex flex-wrap gap-2">
              {ids.length === 0 && <p className="text-[13px] text-text-muted">Nincs beállítva felelős.</p>}
              {ids.map((id) => (
                <span
                  key={id}
                  className="flex items-center gap-1.5 rounded-[var(--radius)] bg-surface-3 px-2.5 py-1 text-[13px] text-text-primary"
                >
                  {employeeById.get(id)?.full_name ?? `#${id}`}
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => save({ ...value, [side.key]: ids.filter((x) => x !== id) })}
                    className="text-text-muted transition-colors hover:text-text-danger disabled:opacity-50"
                    title="Eltávolítás"
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>

            <SearchableIdPicker
              value={null}
              options={available.map((e) => ({ id: e.id, label: e.full_name, sublabel: e.email, group: e.tipus }))}
              onChange={(next) => {
                if (next !== null) save({ ...value, [side.key]: [...ids, next] });
              }}
              placeholder="Felelős hozzáadása…"
              disabled={busy}
              className="min-w-[240px]"
            />
          </div>
        );
      })}

      {error && <p className="text-[12px] text-text-danger">{error}</p>}
      {saved && !error && <p className="text-[12px] text-text-success">Mentve.</p>}
    </div>
  );
}
