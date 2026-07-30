"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";
import type { TimerState } from "@/lib/api";

function formatMinutes(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return h > 0 ? `${h} óra ${m} perc` : `${m} perc`;
}

function formatElapsedSince(startIso: string, now: Date): string {
  const start = new Date(startIso);
  const totalSeconds = Math.max(0, Math.floor((now.getTime() - start.getTime()) / 1000));
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

/** Start/Stop időmérés egy Utómunka anyagon - egyénenként külön követi, ki
 * mennyit dolgozott (lásd services/deliverable_actions.py timer_*), hogy az
 * óradíjjal felszorozva ki lehessen számolni a vágás tényleges költségét. */
export function TimerControls({
  deliverableId,
  initialState,
  showCost = true,
  isAdmin = false,
}: {
  deliverableId: number;
  initialState: TimerState | null;
  /** Admin más futó mérését is leállíthatja - egy elfelejtett mérőt egyébként
   * csak az tudna lezárni, aki elindította (lásd stop_timer_for_employee). */
  isAdmin?: boolean;
  /** A forint összegek csak annak látszanak, akinek a Pénzügy oldalhoz van
   * hozzáférése - a backend amúgy is üresen adja vissza nekik (lásd
   * services/deliverable_actions._may_see_costs). */
  showCost?: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const running = Boolean(initialState?.my_running_since);
  // Az óra akkor is ketyegjen, ha nem én mérek, hanem valaki más - különben a
  // "kinél fut" lista ideje befagyna a betöltés pillanatában.
  const barkiMer = running || (initialState?.running.length ?? 0) > 0;

  useEffect(() => {
    if (!barkiMer) return;
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, [barkiMer]);

  /** A saját sorunkat a fenti Start/Stop gomb kezeli - ott ne jelenjen meg
   * még egy "Leállítás". */
  function isMine(employeeId: number): boolean {
    return running && initialState?.running.some((r) => r.employee_id === employeeId && r.since === initialState.my_running_since) === true;
  }

  async function stopFor(employeeId: number, nev: string) {
    if (!(await confirm(`Leállítod ${nev} futó időmérését?`))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}/timer/stop/${employeeId}`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleClick() {
    setBusy(true);
    try {
      const path = running ? "stop" : "start";
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}/timer/${path}`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={handleClick}
          className={`rounded-[var(--radius)] px-4 py-1.5 text-[13px] font-medium disabled:opacity-50 ${
            running ? "bg-bg-danger text-text-danger" : "bg-bg-success text-text-success"
          }`}
        >
          {running ? "Stop" : "Start"}
        </button>
        {/* Az eltelt idő a szerveren és a böngészőben más másodpercnél jár (a
            kettő között eltelik némi idő) - ez a szöveg definíció szerint
            eltér, ezért suppressHydrationWarning van rajta. */}
        {running && initialState?.my_running_since && (
          <span suppressHydrationWarning className="text-[13px] tabular-nums text-text-secondary">
            {formatElapsedSince(initialState.my_running_since, now)}
          </span>
        )}
      </div>

      {/* Az ÉPP FUTÓ mérések névvel - enélkül csak egy csupasz óra ketyegett,
          amiből nem derült ki, kihez tartozik (és a másokét nem is mutatta). */}
      {initialState && initialState.running.length > 0 && (
        <div className="space-y-1">
          {initialState.running.map((r) => (
            <div key={r.employee_id} className="flex items-center justify-between gap-2 text-[12px]">
              <span className="text-text-primary">{r.full_name}</span>
              <span className="flex items-center gap-2">
                <span suppressHydrationWarning className="tabular-nums text-text-warning">
                  {formatElapsedSince(r.since, now)} · fut
                </span>
                {isAdmin && !isMine(r.employee_id) && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => stopFor(r.employee_id, r.full_name)}
                    className="rounded-[var(--radius)] border border-border px-1.5 py-0.5 text-[11px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                  >
                    Leállítás
                  </button>
                )}
              </span>
            </div>
          ))}
        </div>
      )}

      {initialState && initialState.by_employee.length > 0 && (
        <div className="space-y-1">
          {initialState.by_employee.map((e) => (
            <div key={e.employee_id} className="flex items-center justify-between text-[12px] text-text-secondary">
              <span>{e.full_name}</span>
              <span>
                {formatMinutes(e.total_minutes)}
                {showCost && e.total_cost != null && <span className="text-text-muted"> · {Math.round(e.total_cost)} Ft</span>}
              </span>
            </div>
          ))}
          <div className="mt-1.5 flex items-center justify-between border-t border-border pt-1.5 text-[12px] font-medium text-text-primary">
            <span>Összesen</span>
            <span>
              {formatMinutes(initialState.total_minutes)}
              {showCost && initialState.total_cost != null && (
                <span className="text-text-muted"> · {Math.round(initialState.total_cost)} Ft</span>
              )}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
