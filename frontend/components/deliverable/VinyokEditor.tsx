"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

/** "Vinyók" - többválasztós lista, hogy az adott anyag milyen fizikai/digitális
 * hordozón (vinyón) van rajta. A korábban valaha használt értékek közül
 * checkboxokkal választható, plusz szabadon hozzáadható új érték is. */
export function VinyokEditor({
  deliverableId,
  knownOptions,
  currentValues,
}: {
  deliverableId: number;
  knownOptions: string[];
  currentValues: string[];
}) {
  const router = useRouter();
  const [selected, setSelected] = useState<Set<string>>(new Set(currentValues));
  const [newValue, setNewValue] = useState("");
  const [busy, setBusy] = useState(false);

  const allOptions = Array.from(new Set([...knownOptions, ...currentValues])).sort();

  async function save(next: Set<string>) {
    setSelected(next);
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}`, {
        method: "PATCH",
        body: JSON.stringify({ vinyok: Array.from(next) }),
      });
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

  function toggle(value: string) {
    const next = new Set(selected);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    save(next);
  }

  function addNew() {
    const value = newValue.trim();
    if (!value) return;
    const next = new Set(selected);
    next.add(value);
    setNewValue("");
    save(next);
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1.5">
        {allOptions.length === 0 && <p className="text-[13px] text-text-muted">Még nincs vinyó felvéve.</p>}
        {allOptions.map((opt) => (
          <label key={opt} className="flex items-center gap-1.5 text-[13px] text-text-secondary">
            <input type="checkbox" disabled={busy} checked={selected.has(opt)} onChange={() => toggle(opt)} />
            {opt}
          </label>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={newValue}
          onChange={(e) => setNewValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addNew();
            }
          }}
          placeholder="Új vinyó neve…"
          className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
        />
        <button
          type="button"
          disabled={busy || !newValue.trim()}
          onClick={addNew}
          className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          Hozzáadás
        </button>
      </div>
    </div>
  );
}
