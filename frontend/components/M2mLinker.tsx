"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { SearchableIdPicker } from "@/components/SearchableIdPicker";

type Option = { id: number; label: string; href?: string; sublabel?: string | null; group?: string | null };

/** Many-to-many kapcsolat (pl. Project.equipment_ids) szerkesztése: már
 * hozzárendelt elemek "chip" listája (✕ gombbal leválasztható), plusz egy
 * legördülő a még nem hozzárendelt elemek közül. A teljes új id-listát küldi
 * PATCH-csel - a backend m2m_fields mechanizmusa lecseréli a kapcsolatot. */
export function M2mLinker({
  patchPath,
  fieldName,
  currentIds,
  options,
  addLabel = "Hozzáadás",
  emptyText = "Nincs hozzárendelve.",
  onAdded,
}: {
  patchPath: string;
  fieldName: string;
  currentIds: number[];
  options: Option[];
  addLabel?: string;
  emptyText?: string;
  /** SIKERES hozzáadás után hívjuk, a hozzáadott elem id-jével. A stáblistánál
   * ebből nyílik meg a "mennyiért vállalja ezt a napot" kérdés (lásd
   * StabLinker) - a kapcsolat maga ettől függetlenül már létrejött. */
  onAdded?: (id: number) => void;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState("");

  const optionById = new Map(options.map((o) => [o.id, o]));
  const linked = currentIds.map((id) => optionById.get(id)).filter((o): o is Option => !!o);
  const available = options.filter((o) => !currentIds.includes(o.id));

  async function patch(newIds: number[], hozzaadott?: number) {
    setBusy(true);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify({ [fieldName]: newIds }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      if (hozzaadott !== undefined) onAdded?.(hozzaadott);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        {linked.length === 0 && <p className="text-[13px] text-text-muted">{emptyText}</p>}
        {linked.map((o) => (
          <span key={o.id} className="flex items-center gap-1.5 rounded-[var(--radius)] bg-surface-3 px-2.5 py-1 text-[13px]">
            {o.href ? (
              <a href={o.href} className="text-text-accent hover:underline">
                {o.label}
              </a>
            ) : (
              o.label
            )}
            <button
              type="button"
              disabled={busy}
              onClick={() => patch(currentIds.filter((id) => id !== o.id))}
              className="text-text-muted hover:text-text-danger disabled:opacity-50"
              title="Leválasztás"
            >
              ✕
            </button>
          </span>
        ))}
      </div>
      {available.length > 0 && (
        <div className="flex items-center gap-2">
          {/* Ugyanaz a gépeléssel kereshető választó, mint a technikánál (lásd
              EquipmentBookingManager) - sok stábtagnál egy sima legördülőben
              végiggörgetni használhatatlan volt. */}
          <SearchableIdPicker
            value={selected ? Number(selected) : null}
            options={available.map((o) => ({ id: o.id, label: o.label, sublabel: o.sublabel, group: o.group }))}
            onChange={(next) => setSelected(next === null ? "" : String(next))}
            placeholder="Keresés név szerint…"
            disabled={busy}
            className="min-w-[240px]"
          />
          <button
            type="button"
            disabled={!selected || busy}
            onClick={() => {
              patch([...currentIds, Number(selected)], Number(selected));
              setSelected("");
            }}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            {addLabel}
          </button>
        </div>
      )}
    </div>
  );
}
