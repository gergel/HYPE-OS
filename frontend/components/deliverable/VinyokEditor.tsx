"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { selectColor } from "@/lib/selectColor";

/** "Vinyók" - legördülő, többválasztós lista (mint egy sima "select", csak
 * egyszerre több érték is kiválasztható), hogy az adott anyag melyik
 * (Notionben rögzített, előre meghatározott sorrendű) fizikai/digitális
 * hordozón (vinyón) van rajta. Csak a megadott opciók közül választható - nem
 * szabadon szerkeszthető szöveg (lásd get_vinyo_options a backend oldalon).
 * Ha egy anyagon régi, azóta a listából törölt érték szerepel, azt is
 * megjelenítjük (kikapcsolható), hogy semmi ne tűnjön el észrevétlenül. */
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
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const extras = currentValues.filter((v) => !knownOptions.includes(v)).sort();
  const allOptions = [...knownOptions, ...extras];
  const selectedList = allOptions.filter((opt) => selected.has(opt));

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

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
    <div ref={containerRef} className="relative w-full max-w-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full flex-wrap items-center gap-1 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-left text-[13px] focus:outline-none"
      >
        {selectedList.length === 0 ? (
          <span className="text-text-muted italic">Válassz vinyót…</span>
        ) : (
          selectedList.map((opt) => (
            <span
              key={opt}
              className="inline-flex items-center gap-1 rounded-[var(--radius)] px-1.5 py-0.5 text-[12px]"
              style={{ background: selectColor(opt).bg, color: selectColor(opt).text }}
            >
              {opt}
            </span>
          ))
        )}
        <span className="ml-auto shrink-0 text-text-muted">▾</span>
      </button>
      {open && (
        <div className="absolute z-10 mt-1 max-h-72 w-full min-w-[16rem] overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-1.5 shadow-lg">
          {allOptions.map((opt) => (
            <label key={opt} className="flex items-center gap-1.5 rounded px-1.5 py-1 text-[13px] text-text-secondary hover:bg-surface-3">
              <input type="checkbox" disabled={busy} checked={selected.has(opt)} onChange={() => toggle(opt)} />
              {opt}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
