"use client";

import { useEffect, useRef, useState } from "react";
import { Trash2 } from "lucide-react";
import {
  OPERATOR_LABELS,
  isActiveRule,
  needsValue,
  operatorsFor,
  type ColumnKind,
  type FilterOperator,
  type FilterRule,
} from "@/lib/tableFilters";
import { KeresosSelect } from "@/components/KeresosSelect";

export type FilterColumn = {
  header: string;
  kind: ColumnKind;
  /** Az oszlopban ténylegesen előforduló értékek - egyenlő/nem egyenlő
   * művelethez ezekből lehet legördülő listából választani. */
  options?: string[];
};

/** Ezeknél a műveleteknél PONTOS érték kell, tehát van értelme listából
 * választani. A "tartalmazza"/"ezzel kezdődik" jellegűeknél épp az a lényeg,
 * hogy töredéket lehessen beírni - ott marad a szabad szöveg. */
const LISTAS_MUVELETEK: FilterOperator[] = ["is", "isNot"];

const selectClass =
  "rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary focus:outline-none";

/** Mezőnkénti szűrő-építő a listaoldalak táblái fölé (Notion-mintára):
 * "+ Szűrő" -> oszlopválasztó kereshető listával -> szabály-sor
 * (Ahol [oszlop] [művelet] [érték]). Több szabály ÉS kapcsolatban van.
 *
 * Kizárólag megjelenítési állapotot kezel - a tényleges szűrés az
 * InteractiveTableClient-ben fut a lib/tableFilters matchesAllRules-szal. */
export function TableFilterBuilder({
  columns,
  rules,
  onChange,
}: {
  columns: FilterColumn[];
  rules: FilterRule[];
  onChange: (rules: FilterRule[]) => void;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (!containerRef.current?.contains(e.target as Node)) {
        setPickerOpen(false);
        setPanelOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  function addRule(columnIndex: number) {
    const operator = operatorsFor(columns[columnIndex].kind)[0];
    onChange([...rules, { id: nextId.current++, columnIndex, operator, value: "" }]);
    setPickerOpen(false);
    setPanelOpen(true);
    setSearch("");
  }

  function updateRule(id: number, patch: Partial<FilterRule>) {
    onChange(rules.map((rule) => (rule.id === id ? { ...rule, ...patch } : rule)));
  }

  function removeRule(id: number) {
    const next = rules.filter((rule) => rule.id !== id);
    onChange(next);
    if (next.length === 0) setPanelOpen(false);
  }

  const activeCount = rules.filter(isActiveRule).length;
  const matching = columns
    .map((col, index) => ({ ...col, index }))
    .filter((col) => col.header.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <div ref={containerRef} className="relative flex flex-wrap items-center gap-2">
      {rules.length > 0 && (
        <button
          type="button"
          onClick={() => setPanelOpen((v) => !v)}
          className={`rounded-[var(--radius)] border px-2.5 py-1.5 text-[12px] transition-colors ${
            activeCount > 0
              ? "border-transparent bg-bg-accent text-text-accent"
              : "border-border text-text-secondary hover:bg-surface-3"
          }`}
        >
          {activeCount > 0 ? `${activeCount} szűrő` : `${rules.length} szűrő (üres)`} ▾
        </button>
      )}

      <button
        type="button"
        onClick={() => {
          setPickerOpen((v) => !v);
          setSearch("");
        }}
        className="btn btn-ghost !px-2.5 !py-1.5 !text-[12px]"
      >
        + Szűrő
      </button>

      {pickerOpen && (
        <div className="fade-in absolute left-0 top-full z-40 mt-2 w-[280px] rounded-[var(--radius-lg)] border border-border-strong bg-surface-2 p-2 shadow-[0_16px_40px_-24px_rgba(0,0,0,0.9)]">
          <input
            autoFocus
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Mező keresése…"
            className="field mb-2 w-full"
          />
          <div className="max-h-[280px] overflow-y-auto">
            {matching.length === 0 && <p className="px-1 py-1.5 text-[12px] text-text-muted">Nincs ilyen mező.</p>}
            {matching.map((col) => (
              <button
                key={col.index}
                type="button"
                onClick={() => addRule(col.index)}
                className="block w-full truncate rounded-[var(--radius)] px-2 py-1.5 text-left text-[13px] text-text-primary transition-colors hover:bg-surface-3"
              >
                {col.header}
              </button>
            ))}
          </div>
        </div>
      )}

      {panelOpen && rules.length > 0 && (
        <div className="fade-in absolute left-0 top-full z-40 mt-2 w-[520px] max-w-[92vw] rounded-[var(--radius-lg)] border border-border-strong bg-surface-2 p-4 shadow-[0_16px_40px_-24px_rgba(0,0,0,0.9)]">
          <div className="space-y-2">
            {rules.map((rule, index) => {
              const kind = columns[rule.columnIndex]?.kind ?? "text";
              const options = columns[rule.columnIndex]?.options;
              return (
                <div key={rule.id} className="flex flex-wrap items-center gap-2">
                  <span className="w-10 text-[12px] text-text-muted">{index === 0 ? "Ahol" : "és"}</span>
                  <KeresosSelect
                    value={String(rule.columnIndex)}
                    options={columns.map((col, i) => ({ value: String(i), label: col.header }))}
                    onChange={(ertek) => {
                      const columnIndex = Number(ertek);
                      const operators = operatorsFor(columns[columnIndex].kind);
                      updateRule(rule.id, {
                        columnIndex,
                        operator: operators.includes(rule.operator) ? rule.operator : operators[0],
                      });
                    }}
                    className="w-[150px]"
                  />
                  <select
                    value={rule.operator}
                    onChange={(e) => updateRule(rule.id, { operator: e.target.value as FilterOperator })}
                    className={selectClass}
                  >
                    {operatorsFor(kind).map((op) => (
                      <option key={op} value={op}>
                        {OPERATOR_LABELS[op]}
                      </option>
                    ))}
                  </select>
                  {!needsValue(rule.operator) ? (
                    <span className="flex-1" />
                  ) : options && LISTAS_MUVELETEK.includes(rule.operator) ? (
                    // Az oszlopban előforduló értékek listája - állapot-jellegű
                    // mezőknél így nem kell kitalálni, pontosan mit kell beírni.
                    <KeresosSelect
                      value={rule.value || null}
                      options={options.map((opt) => ({ value: opt, label: opt }))}
                      onChange={(ertek) => updateRule(rule.id, { value: ertek })}
                      placeholder="Válassz értéket…"
                      className="min-w-0 flex-1"
                    />
                  ) : (
                    <input
                      value={rule.value}
                      onChange={(e) => updateRule(rule.id, { value: e.target.value })}
                      placeholder="Érték"
                      className="field min-w-0 flex-1 !py-1 !text-[12px]"
                    />
                  )}
                  <button
                    type="button"
                    onClick={() => removeRule(rule.id)}
                    title="Szabály törlése"
                    className="rounded-[var(--radius)] p-1 text-text-muted transition-colors hover:bg-surface-3 hover:text-text-danger"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-border pt-2">
            <button
              type="button"
              onClick={() => {
                setPickerOpen(true);
                setPanelOpen(false);
              }}
              className="text-[12px] text-text-accent hover:underline"
            >
              + Szabály hozzáadása
            </button>
            <button
              type="button"
              onClick={() => {
                onChange([]);
                setPanelOpen(false);
              }}
              className="text-[12px] text-text-muted transition-colors hover:text-text-danger"
            >
              Összes szűrő törlése
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
