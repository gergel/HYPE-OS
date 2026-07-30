"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";
import type { JsonRecord } from "@/lib/api";

function formatDateTime(value: unknown): string {
  if (typeof value !== "string" || !value) return "–";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("hu-HU", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatPerc(minutes: number | null): string {
  if (minutes === null) return "–";
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return h > 0 ? `${h} ó ${m} p` : `${m} p`;
}

/** Egy sor percének helyben szerkesztése. Kattintásra beviteli mezővé válik,
 * Enterre/elkattintásra ment. */
function PercCella({
  deliverableId,
  timesheetId,
  minutes,
  canEdit,
}: {
  deliverableId: number;
  timesheetId: number;
  minutes: number | null;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(minutes === null ? "" : String(minutes));
  const [shown, setShown] = useState(minutes);
  const [busy, setBusy] = useState(false);

  async function save() {
    const next = Number(draft);
    setEditing(false);
    if (draft.trim() === "" || Number.isNaN(next) || next === shown) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}/timesheets/${timesheetId}/percek`, {
        method: "POST",
        body: JSON.stringify({ minutes: next }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setShown(next);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (!canEdit) return <span>{formatPerc(shown)}</span>;

  if (!editing) {
    return (
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          setDraft(shown === null ? "" : String(shown));
          setEditing(true);
        }}
        className="rounded px-1 text-right hover:bg-surface-3 disabled:opacity-50"
        title="Kattints a perc javításához"
      >
        {busy ? "Mentés…" : formatPerc(shown)}
      </button>
    );
  }

  return (
    <input
      type="number"
      min={0}
      autoFocus
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={save}
      onKeyDown={(e) => {
        if (e.key === "Enter") save();
        if (e.key === "Escape") setEditing(false);
      }}
      className="w-20 rounded-[var(--radius)] border border-border bg-surface-2 px-1.5 py-0.5 text-right text-[13px] text-text-primary focus:outline-none"
    />
  );
}

/** Ki mennyi időt töltött ezzel az anyaggal - és a perc UTÓLAG JAVÍTHATÓ.
 * Erre azért van szükség, mert az időmérőt el lehet felejteni leállítani (ha
 * egész éjjel futott, a rögzített idő értelmetlen), és az abból számolt
 * költség is a Pénzügybe kerül. A javításkor a backend az akkori órabérrel
 * újraszámolja a költséget is (lásd set_timesheet_minutes). */
export function TimesheetMinutesTable({
  deliverableId,
  rows,
  employeeNameById,
  canEdit,
  showCost,
}: {
  deliverableId: number;
  rows: JsonRecord[];
  employeeNameById: Record<number, string>;
  canEdit: boolean;
  /** A költség oszlop csak annak látszik, akinek a Pénzügy oldalhoz van
   * hozzáférése - a vágóknak jellemzően nincs, nekik az idő releváns. */
  showCost: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busyId, setBusyId] = useState<number | null>(null);

  if (rows.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs munkaidő-elszámolás ehhez az anyaghoz.</p>;
  }

  async function remove(id: number, ki: string) {
    if (!(await confirm(`Biztosan törlöd ${ki} munkaidő-sorát?`))) return;
    setBusyId(id);
    try {
      const res = await authFetch(`/api/v1/timesheets/${id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusyId(null);
    }
  }

  const osszesen = rows.reduce((sum, r) => sum + (typeof r.time_minutes === "number" ? r.time_minutes : 0), 0);

  return (
    <table className="w-full border-collapse text-[13px]">
      <thead>
        <tr className="border-b border-border">
          <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Ki</th>
          <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Kezdés</th>
          <th className="py-1.5 pr-4 text-left font-medium text-text-secondary">Vége</th>
          <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Idő</th>
          {showCost && <th className="py-1.5 pr-4 text-right font-medium text-text-secondary">Költség</th>}
          <th className="py-1.5" />
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const id = Number(r.id);
          const ki = employeeNameById[Number(r.employee_id)] ?? `#${r.employee_id}`;
          const fut = !r.end_date;
          return (
            <tr key={id} className="border-b border-border last:border-0">
              <td className="py-2 pr-4">{ki}</td>
              <td className="py-2 pr-4 text-text-secondary">{formatDateTime(r.start_date)}</td>
              <td className="py-2 pr-4 text-text-secondary">
                {fut ? <span className="text-text-warning">még fut</span> : formatDateTime(r.end_date)}
              </td>
              <td className="py-2 pr-4 text-right whitespace-nowrap">
                <PercCella
                  deliverableId={deliverableId}
                  timesheetId={id}
                  minutes={typeof r.time_minutes === "number" ? r.time_minutes : null}
                  canEdit={canEdit}
                />
              </td>
              {showCost && (
                <td className="py-2 pr-4 text-right whitespace-nowrap text-text-secondary">
                  {typeof r.koltseg === "number" ? `${r.koltseg.toLocaleString("hu-HU")} Ft` : "–"}
                </td>
              )}
              <td className="py-2 text-right">
                {canEdit && (
                  <button
                    type="button"
                    disabled={busyId === id}
                    onClick={() => remove(id, ki)}
                    className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                    title="Sor törlése"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </td>
            </tr>
          );
        })}
        <tr>
          <td className="py-2 pr-4 text-text-secondary" colSpan={3}>
            Összesen
          </td>
          <td className="py-2 pr-4 text-right font-medium whitespace-nowrap text-text-primary">{formatPerc(osszesen)}</td>
          <td colSpan={showCost ? 2 : 1} />
        </tr>
      </tbody>
    </table>
  );
}
