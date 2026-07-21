"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { ICON_NAMES } from "@/components/icon-map";

type FieldOption = { key: string; label: string };
type DbTab = { tab_key: string; label: string; icon: string | null; field_keys: string[] };
type EntityOption = { entityType: string; label: string; availableFields: FieldOption[] };

const OTHER_TAB_KEY = "_other";

function slugifyTabKey(label: string): string {
  return (
    label
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || `ful_${Date.now()}`
  );
}

/** Egy entitástípus fül-elrendezésének szerkesztője - admin átrendezheti,
 * mely mezők melyik fülbe kerüljenek, hány fül legyen, milyen néven/ikonnal
 * (lásd backend/app/services/detail_tabs.py). Amit egyik fül sem tartalmaz,
 * az automatikusan a szintetikus "Egyéb" fülre esik a részletnézeteken - ezt
 * itt csak tájékoztatásul soroljuk fel, nem menthető külön. */
function EntityTabEditor({ entityType, label: entityLabel, availableFields, initialTabs }: EntityOption & { initialTabs: DbTab[] }) {
  const router = useRouter();
  const [tabs, setTabs] = useState<DbTab[]>(initialTabs.map((t) => ({ ...t, field_keys: [...t.field_keys] })));
  const [busy, setBusy] = useState(false);

  const assignedFields = new Set(tabs.flatMap((t) => t.field_keys));
  const unassigned = availableFields.filter((f) => !assignedFields.has(f.key));

  function addTab() {
    setTabs((prev) => [...prev, { tab_key: `uj_ful_${prev.length}`, label: "Új fül", icon: null, field_keys: [] }]);
  }

  function removeTab(index: number) {
    setTabs((prev) => prev.filter((_, i) => i !== index));
  }

  function moveTab(index: number, dir: -1 | 1) {
    setTabs((prev) => {
      const next = [...prev];
      const target = index + dir;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  }

  function updateLabel(index: number, label: string) {
    setTabs((prev) => prev.map((t, i) => (i === index ? { ...t, label, tab_key: t.tab_key.startsWith("uj_ful_") ? slugifyTabKey(label) : t.tab_key } : t)));
  }

  function updateIcon(index: number, icon: string) {
    setTabs((prev) => prev.map((t, i) => (i === index ? { ...t, icon: icon || null } : t)));
  }

  function toggleField(index: number, fieldKey: string) {
    setTabs((prev) =>
      prev.map((t, i) => {
        if (i !== index) return t;
        const has = t.field_keys.includes(fieldKey);
        return { ...t, field_keys: has ? t.field_keys.filter((f) => f !== fieldKey) : [...t.field_keys, fieldKey] };
      }),
    );
  }

  async function save() {
    setBusy(true);
    try {
      const body = { tabs: tabs.map((t) => ({ tab_key: t.tab_key, label: t.label, icon: t.icon, field_keys: t.field_keys })) };
      const res = await authFetch(`/api/v1/detail-tabs/${entityType}`, { method: "PUT", body: JSON.stringify(body) });
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
    <div className="space-y-3">
      <p className="text-[12px] text-text-muted">
        {entityLabel} - {tabs.length} fül. Ami egyik fülhöz sincs rendelve ({unassigned.length} mező), az a részletnézeten
        automatikusan az &quot;Egyéb&quot; fülre kerül.
      </p>

      {tabs.map((tab, index) => (
        <details key={index} className="rounded-[var(--radius)] border border-border p-3" open={tabs.length <= 3}>
          <summary className="flex cursor-pointer items-center justify-between gap-2 text-[13px] font-medium text-text-primary">
            <span>
              {tab.label || "(névtelen fül)"} <span className="text-text-muted">({tab.field_keys.length} mező)</span>
            </span>
            <span className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
              <button type="button" onClick={() => moveTab(index, -1)} disabled={index === 0} className="rounded border border-border px-1.5 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-30">
                ↑
              </button>
              <button type="button" onClick={() => moveTab(index, 1)} disabled={index === tabs.length - 1} className="rounded border border-border px-1.5 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-30">
                ↓
              </button>
              <button type="button" onClick={() => removeTab(index)} className="rounded border border-text-danger/40 px-1.5 text-[12px] text-text-danger hover:bg-bg-danger">
                Törlés
              </button>
            </span>
          </summary>

          <div className="mt-3 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={tab.label}
                onChange={(e) => updateLabel(index, e.target.value)}
                placeholder="Fül neve"
                className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
              />
              <select
                value={tab.icon ?? ""}
                onChange={(e) => updateIcon(index, e.target.value)}
                className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
              >
                <option value="">(nincs ikon)</option>
                {ICON_NAMES.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
              {availableFields.map((f) => (
                <label key={f.key} className="flex items-center gap-1.5 text-[12px] text-text-secondary">
                  <input type="checkbox" checked={tab.field_keys.includes(f.key)} onChange={() => toggleField(index, f.key)} />
                  {f.label}
                </label>
              ))}
            </div>
          </div>
        </details>
      ))}

      <div className="flex items-center gap-3">
        <button type="button" onClick={addTab} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3">
          + Új fül
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={save}
          className="rounded-[var(--radius)] border border-text-accent/40 px-3 py-1.5 text-[13px] text-text-accent hover:bg-surface-3 disabled:opacity-50"
        >
          Mentés
        </button>
      </div>
    </div>
  );
}

/** Admin fül-elrendezés szerkesztő az ÖSSZES fület-alapú részletnézettel
 * rendelkező entitáshoz (Projekt, Ügyfél, Project Code, Crew, Felszerelés,
 * Kampány, Feladat, Utómunka) - lásd Beállítások oldal. Egyszerre csak egy
 * entitástípus szerkesztője jelenik meg (választó gombokkal), hogy a nagy
 * mezőszámú entitásoknál (pl. Projekt ~140 mező) ne kelljen egyszerre minden
 * entitás teljes checkbox-listáját renderelni. */
export function DetailTabEditor({ entities, initialConfigsByEntity }: { entities: EntityOption[]; initialConfigsByEntity: Record<string, DbTab[]> }) {
  const [selected, setSelected] = useState(entities[0]?.entityType ?? "");
  const entity = entities.find((e) => e.entityType === selected);

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {entities.map((e) => (
          <button
            key={e.entityType}
            type="button"
            onClick={() => setSelected(e.entityType)}
            className={`rounded-[var(--radius)] border px-2.5 py-1 text-[12px] transition-colors ${
              selected === e.entityType
                ? "border-text-accent/50 bg-surface-3 text-text-primary"
                : "border-border text-text-secondary hover:bg-surface-3"
            }`}
          >
            {e.label}
          </button>
        ))}
      </div>
      {entity && (
        <EntityTabEditor
          key={entity.entityType}
          entityType={entity.entityType}
          label={entity.label}
          availableFields={entity.availableFields}
          initialTabs={(initialConfigsByEntity[entity.entityType] ?? []).filter((t) => t.tab_key !== OTHER_TAB_KEY)}
        />
      )}
    </div>
  );
}
