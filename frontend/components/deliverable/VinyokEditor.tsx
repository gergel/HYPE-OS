"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

/** "Vinyók" - többválasztós lista, hogy az adott anyag melyik (Notionben
 * rögzített, előre meghatározott sorrendű) fizikai/digitális hordozón
 * (vinyón) van rajta. Csak a megadott opciók közül választható checkboxokkal
 * - nem szabadon szerkeszthető szöveg (lásd get_vinyo_options a backend
 * oldalon). Ha egy anyagon régi, azóta a listából törölt érték szerepel,
 * azt is megjelenítjük (kikapcsolható), hogy semmi ne tűnjön el észrevétlenül. */
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
  const [busy, setBusy] = useState(false);

  const extras = currentValues.filter((v) => !knownOptions.includes(v)).sort();
  const allOptions = [...knownOptions, ...extras];

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

  return (
    <div>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {allOptions.length === 0 && <p className="text-[13px] text-text-muted">Még nincs vinyó felvéve.</p>}
        {allOptions.map((opt) => (
          <label key={opt} className="flex items-center gap-1.5 text-[13px] text-text-secondary">
            <input type="checkbox" disabled={busy} checked={selected.has(opt)} onChange={() => toggle(opt)} />
            {opt}
          </label>
        ))}
      </div>
    </div>
  );
}
