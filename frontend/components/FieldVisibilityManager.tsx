"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type FieldOption = { key: string; label: string };

/** Egy munkatárs egy entitástípushoz tartozó mező-láthatóságának beállítása
 * (Beállítások oldal) - mely mezők jelenjenek meg a részletnézeten. Egyénenként
 * állítható, csak admin mentheti (lásd backend require_roles). */
export function FieldVisibilityManager({
  patchPath,
  entityLabel,
  availableFields,
  initialVisible,
}: {
  patchPath: string;
  entityLabel: string;
  availableFields: FieldOption[];
  initialVisible: string[] | null;
}) {
  const router = useRouter();
  const [showAll, setShowAll] = useState(!initialVisible || initialVisible.length === 0);
  const [selected, setSelected] = useState<Set<string>>(
    new Set(initialVisible && initialVisible.length > 0 ? initialVisible : availableFields.map((f) => f.key)),
  );
  const [busy, setBusy] = useState(false);

  function toggle(key: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function save() {
    setBusy(true);
    try {
      const body = { visible_fields: showAll ? null : Array.from(selected) };
      const res = await authFetch(patchPath, { method: "PUT", body: JSON.stringify(body) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="rounded-[var(--radius)] border border-border p-3">
      <summary className="cursor-pointer text-[13px] font-medium text-text-primary">
        {entityLabel} <span className="text-text-muted">({availableFields.length} mező)</span>
      </summary>
      <div className="mt-3">
        <label className="mb-3 flex items-center gap-2 text-[13px] text-text-secondary">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          Minden mező látszik (nincs szűrés)
        </label>
        {!showAll && (
          <>
            <div className="mb-2 flex gap-2">
              <button
                type="button"
                onClick={() => setSelected(new Set())}
                className="text-[12px] text-text-accent hover:underline"
              >
                Összes kikapcsolása
              </button>
              <span className="text-text-muted">·</span>
              <button
                type="button"
                onClick={() => setSelected(new Set(availableFields.map((f) => f.key)))}
                className="text-[12px] text-text-accent hover:underline"
              >
                Összes bekapcsolása
              </button>
            </div>
            <div className="mb-3 grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
              {availableFields.map((f) => (
                <label key={f.key} className="flex items-center gap-1.5 text-[12px] text-text-secondary">
                  <input type="checkbox" checked={selected.has(f.key)} onChange={() => toggle(f.key)} />
                  {f.label}
                </label>
              ))}
            </div>
          </>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={save}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          Mentés
        </button>
      </div>
    </details>
  );
}
