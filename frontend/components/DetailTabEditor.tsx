"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { ICON_NAMES } from "@/components/icon-map";

type FieldOption = { key: string; label: string };
type DbTab = { tab_key: string; label: string; icon: string | null; field_keys: string[] };
type EntityOption = { entityType: string; label: string; availableFields: FieldOption[] };

const OTHER_TAB_KEY = "_other";
const UNASSIGNED_VALUE = "";

function slugifyTabKey(label: string, existing: Set<string>): string {
  const base =
    label
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "ful";
  let key = base;
  let n = 2;
  while (existing.has(key)) key = `${base}_${n++}`;
  return key;
}

type TabMeta = { tab_key: string; label: string; icon: string | null };

/** Egy entitástípus fül-elrendezésének szerkesztője. A mezőnkénti hozzárendelés
 * EGYETLEN legördülőt kap mezőnként (melyik fülbe kerüljön - vagy "Egyéb"),
 * nem N db checkboxot fülönként ismételve - így egy nagy mezőszámú entitásnál
 * (pl. Projekt ~140, Project Code ~75 mező) a mezőlistát csak egyszer kell
 * végignézni, és egy mező sosem kerülhet véletlenül két fülbe egyszerre.
 * A fülek maguk (név/ikon/sorrend) egy külön, kompakt listában szerkeszthetők
 * felül. Amit egy mezőhöz sem rendelünk explicit fülhöz, az a részletnézeten
 * automatikusan a szintetikus "Egyéb" fülre esik. */
function EntityTabEditor({ entityType, label: entityLabel, availableFields, initialTabs }: EntityOption & { initialTabs: DbTab[] }) {
  const router = useRouter();
  const [tabs, setTabs] = useState<TabMeta[]>(initialTabs.map((t) => ({ tab_key: t.tab_key, label: t.label, icon: t.icon })));
  const [assignment, setAssignment] = useState<Map<string, string>>(() => {
    const map = new Map<string, string>();
    for (const t of initialTabs) {
      for (const fieldKey of t.field_keys) {
        if (!map.has(fieldKey)) map.set(fieldKey, t.tab_key);
      }
    }
    return map;
  });
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);

  const fieldCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const tabKey of assignment.values()) counts.set(tabKey, (counts.get(tabKey) ?? 0) + 1);
    return counts;
  }, [assignment]);
  const unassignedCount = availableFields.length - assignment.size;

  const filteredFields = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return availableFields;
    return availableFields.filter((f) => f.label.toLowerCase().includes(q) || f.key.toLowerCase().includes(q));
  }, [availableFields, search]);

  function addTab() {
    setTabs((prev) => {
      const existingKeys = new Set(prev.map((t) => t.tab_key));
      return [...prev, { tab_key: slugifyTabKey("Új fül", existingKeys), label: "Új fül", icon: null }];
    });
  }

  function removeTab(index: number) {
    const removedKey = tabs[index].tab_key;
    setTabs((prev) => prev.filter((_, i) => i !== index));
    setAssignment((prev) => {
      const next = new Map(prev);
      for (const [field, tabKey] of next) if (tabKey === removedKey) next.delete(field);
      return next;
    });
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
    setTabs((prev) => prev.map((t, i) => (i === index ? { ...t, label } : t)));
  }

  function updateIcon(index: number, icon: string) {
    setTabs((prev) => prev.map((t, i) => (i === index ? { ...t, icon: icon || null } : t)));
  }

  function assignField(fieldKey: string, tabKey: string) {
    setAssignment((prev) => {
      const next = new Map(prev);
      if (tabKey === UNASSIGNED_VALUE) next.delete(fieldKey);
      else next.set(fieldKey, tabKey);
      return next;
    });
  }

  function bulkAssign(fields: FieldOption[], tabKey: string) {
    setAssignment((prev) => {
      const next = new Map(prev);
      for (const f of fields) {
        if (tabKey === UNASSIGNED_VALUE) next.delete(f.key);
        else next.set(f.key, tabKey);
      }
      return next;
    });
  }

  async function save() {
    setBusy(true);
    try {
      const body = {
        tabs: tabs.map((t) => ({
          tab_key: t.tab_key,
          label: t.label,
          icon: t.icon,
          field_keys: availableFields.filter((f) => assignment.get(f.key) === t.tab_key).map((f) => f.key),
        })),
      };
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
    <div className="space-y-4">
      <p className="text-[12px] text-text-muted">
        {entityLabel} - {availableFields.length} mező, {tabs.length} fül. Ami egyik fülhöz sincs rendelve ({unassignedCount} mező),
        az a részletnézeten automatikusan az &quot;Egyéb&quot; fülre kerül.
      </p>

      <div className="space-y-1.5">
        {tabs.map((tab, index) => (
          <div key={tab.tab_key} className="flex flex-wrap items-center gap-1.5 rounded-[var(--radius)] border border-border p-2">
            <span className="w-5 shrink-0 text-center text-[11px] text-text-muted">{index + 1}.</span>
            <input
              type="text"
              value={tab.label}
              onChange={(e) => updateLabel(index, e.target.value)}
              placeholder="Fül neve"
              className="min-w-0 flex-1 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
            />
            <select
              value={tab.icon ?? ""}
              onChange={(e) => updateIcon(index, e.target.value)}
              className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary focus:outline-none"
            >
              <option value="">(nincs ikon)</option>
              {ICON_NAMES.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <span className="text-[11px] text-text-muted">{fieldCounts.get(tab.tab_key) ?? 0} mező</span>
            <button type="button" onClick={() => moveTab(index, -1)} disabled={index === 0} className="rounded border border-border px-1.5 py-0.5 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-30">
              ↑
            </button>
            <button type="button" onClick={() => moveTab(index, 1)} disabled={index === tabs.length - 1} className="rounded border border-border px-1.5 py-0.5 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-30">
              ↓
            </button>
            <button type="button" onClick={() => removeTab(index)} className="btn btn-danger !px-2 !py-1 !text-[12px]">
              Törlés
            </button>
          </div>
        ))}
        <button type="button" onClick={addTab} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3">
          + Új fül
        </button>
      </div>

      <div className="border-t border-border pt-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Mező keresése…"
            className="min-w-0 flex-1 rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
          />
          {tabs.length > 0 && (
            <span className="flex items-center gap-1.5 text-[12px] text-text-muted">
              Találatok:
              <select
                onChange={(e) => {
                  if (e.target.value) bulkAssign(filteredFields, e.target.value);
                  e.target.value = "";
                }}
                defaultValue=""
                className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary focus:outline-none"
              >
                <option value="" disabled>
                  mind ide →
                </option>
                <option value={UNASSIGNED_VALUE}>Egyéb</option>
                {tabs.map((t) => (
                  <option key={t.tab_key} value={t.tab_key}>
                    {t.label}
                  </option>
                ))}
              </select>
            </span>
          )}
        </div>

        <div className="max-h-96 overflow-y-auto rounded-[var(--radius)] border border-border">
          {filteredFields.length === 0 && <p className="p-3 text-[13px] text-text-muted">Nincs találat.</p>}
          {filteredFields.map((f) => (
            <div key={f.key} className="flex items-center justify-between gap-2 border-b border-border px-3 py-1.5 text-[13px] last:border-b-0">
              <span className="text-text-secondary">{f.label}</span>
              <select
                value={assignment.get(f.key) ?? UNASSIGNED_VALUE}
                onChange={(e) => assignField(f.key, e.target.value)}
                className="shrink-0 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary focus:outline-none"
              >
                <option value={UNASSIGNED_VALUE}>Egyéb</option>
                {tabs.map((t) => (
                  <option key={t.tab_key} value={t.tab_key}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </div>

      <button
        type="button"
        disabled={busy}
        onClick={save}
        className="rounded-[var(--radius)] border border-text-accent/40 px-3 py-1.5 text-[13px] text-text-accent hover:bg-surface-3 disabled:opacity-50"
      >
        Mentés
      </button>
    </div>
  );
}

/** Admin fül-elrendezés szerkesztő az ÖSSZES fület-alapú részletnézettel
 * rendelkező entitáshoz (Projekt, Ügyfél, Project Code, Crew, Felszerelés,
 * Kampány, Feladat, Utómunka) - lásd Beállítások oldal. Egyszerre csak egy
 * entitástípus szerkesztője jelenik meg (választó gombokkal), hogy a nagy
 * mezőszámú entitásoknál (pl. Projekt ~140 mező) ne kelljen egyszerre minden
 * entitás teljes mezőlistáját renderelni. */
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
