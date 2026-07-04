"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

export type WidgetOption = { key: string; label: string };

/** Mindenki (nem csak admin) testreszabhatja a saját Dashboardján megjelenő
 * widgeteket - tisztán megjelenítési preferencia, önkiszolgáló (lásd
 * PUT /api/v1/dashboard/config/me, nincs admin-gate). */
export function DashboardCustomizePanel({
  widgets,
  initialVisible,
}: {
  widgets: WidgetOption[];
  initialVisible: string[] | null;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [showAll, setShowAll] = useState(!initialVisible || initialVisible.length === 0);
  const [selected, setSelected] = useState<Set<string>>(
    new Set(initialVisible && initialVisible.length > 0 ? initialVisible : widgets.map((w) => w.key)),
  );
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

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
      const body = { visible_widgets: showAll ? null : Array.from(selected) };
      const res = await authFetch("/api/v1/dashboard/config/me", { method: "PUT", body: JSON.stringify(body) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setOpen(false);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Dashboard testreszabása"
        className="flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
        </svg>
        Testreszabás
      </button>
      {open && (
        <div className="absolute right-0 top-full z-10 mt-2 w-72 rounded-[var(--radius)] border border-border bg-surface-2 p-3 shadow-lg">
          <p className="mb-2 text-[13px] font-medium text-text-primary">Mely widgetek látszódjanak?</p>
          <label className="mb-2 flex items-center gap-2 text-[13px] text-text-secondary">
            <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
            Minden widget látszik
          </label>
          {!showAll && (
            <div className="mb-3 space-y-1.5">
              {widgets.map((w) => (
                <label key={w.key} className="flex items-center gap-1.5 text-[12px] text-text-secondary">
                  <input type="checkbox" checked={selected.has(w.key)} onChange={() => toggle(w.key)} />
                  {w.label}
                </label>
              ))}
            </div>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={save}
            className="w-full rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            Mentés
          </button>
        </div>
      )}
    </div>
  );
}
