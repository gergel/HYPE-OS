"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";
import { elteltPercek, formatEltelt, formatFt, formatPercek, futoKoltseg } from "@/lib/ido";
import type { TimerState } from "@/lib/api";

/** Start/Stop időmérés egy Utómunka anyagon - egyénenként külön követi, ki
 * mennyit dolgozott (lásd services/deliverable_actions.py timer_*), hogy az
 * óradíjjal felszorozva ki lehessen számolni a vágás tényleges költségét.
 *
 * A még FUTÓ mérés ideje ÉS költsége is másodpercenként frissül: az óradíj a
 * mérés indításakor rögzített órabér (TimerRunningEntry.orabere), ugyanaz,
 * amivel a backend a leállításkor számol - így a Stop pillanatában nem ugrik
 * meg az összeg. */
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
  const futok = initialState?.running ?? [];
  // Az óra akkor is ketyegjen, ha nem én mérek, hanem valaki más - különben a
  // "kinél fut" lista ideje befagyna a betöltés pillanatában.
  const barkiMer = running || futok.length > 0;

  useEffect(() => {
    if (!barkiMer) return;
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, [barkiMer]);

  /** A saját sorunkat a fenti Start/Stop gomb kezeli - ott ne jelenjen meg
   * még egy "Leállítás". */
  function isMine(employeeId: number): boolean {
    return running && futok.some((r) => r.employee_id === employeeId && r.since === initialState?.my_running_since);
  }

  // A lezárt sorokból számolt összesítéshez hozzáadjuk a MOST futó méréseket
  // is, hogy a lista és az "Összesen" sor együtt nőjön az órával - különben
  // csak leállítás után derülne ki, hol tart az anyag ideje és költsége.
  const futoPercPerFo = new Map<number, number>();
  const futoKoltsegPerFo = new Map<number, number>();
  for (const r of futok) {
    futoPercPerFo.set(r.employee_id, (futoPercPerFo.get(r.employee_id) ?? 0) + elteltPercek(r.since, now));
    futoKoltsegPerFo.set(r.employee_id, (futoKoltsegPerFo.get(r.employee_id) ?? 0) + futoKoltseg(r.since, r.orabere, now));
  }
  const mertFok = [...new Set([...(initialState?.by_employee ?? []).map((e) => e.employee_id), ...futoPercPerFo.keys()])];
  const osszesites = mertFok.map((employeeId) => {
    const lezart = initialState?.by_employee.find((e) => e.employee_id === employeeId);
    const futoSor = futok.find((r) => r.employee_id === employeeId);
    const vanKoltseg = lezart?.total_cost != null || futoSor?.orabere != null;
    return {
      employee_id: employeeId,
      full_name: lezart?.full_name ?? futoSor?.full_name ?? "Ismeretlen",
      total_minutes: (lezart?.total_minutes ?? 0) + (futoPercPerFo.get(employeeId) ?? 0),
      total_cost: vanKoltseg ? (lezart?.total_cost ?? 0) + (futoKoltsegPerFo.get(employeeId) ?? 0) : null,
      fut: futoSor != null,
    };
  });
  const osszPerc = osszesites.reduce((sum, e) => sum + e.total_minutes, 0);
  const vanBarmiKoltseg = osszesites.some((e) => e.total_cost != null);
  const osszKoltseg = vanBarmiKoltseg ? osszesites.reduce((sum, e) => sum + (e.total_cost ?? 0), 0) : null;

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
            {formatEltelt(initialState.my_running_since, now)}
          </span>
        )}
      </div>

      {/* Az ÉPP FUTÓ mérések névvel - enélkül csak egy csupasz óra ketyegett,
          amiből nem derült ki, kihez tartozik (és a másokét nem is mutatta). */}
      {futok.length > 0 && (
        <div className="mb-3 space-y-1">
          {/* A kulcsban a kezdés is benne van: ugyanahhoz az emberhez
              elvileg egy futó mérés tartozik (a Start ezt kikényszeríti), de
              egy hibás adatból származó második sor így sem borítja fel a
              listát. */}
          {futok.map((r) => (
            <div key={`${r.employee_id}-${r.since}`} className="flex items-center justify-between gap-2 text-[12px]">
              <span className="text-text-primary">{r.full_name}</span>
              <span className="flex items-center gap-2">
                <span suppressHydrationWarning className="tabular-nums text-text-warning">
                  {formatEltelt(r.since, now)}
                  {showCost && r.orabere != null && ` · ${formatFt(futoKoltseg(r.since, r.orabere, now))}`} · fut
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

      {osszesites.length > 0 && (
        <div className="space-y-1">
          {osszesites.map((e) => (
            <div key={e.employee_id} className="flex items-center justify-between text-[12px] text-text-secondary">
              <span>{e.full_name}</span>
              {/* A suppressHydrationWarning nem öröklődik a gyerekekre, ezért a
                  forintos részen külön is ott van - a futó mérés összege a
                  szerveren és a böngészőben definíció szerint eltér. */}
              <span suppressHydrationWarning>
                {formatPercek(e.total_minutes)}
                {showCost && e.total_cost != null && (
                  <span suppressHydrationWarning className="text-text-muted">
                    {" "}
                    · {formatFt(e.total_cost)}
                  </span>
                )}
              </span>
            </div>
          ))}
          <div className="mt-1.5 flex items-center justify-between border-t border-border pt-1.5 text-[12px] font-medium text-text-primary">
            <span>Összesen</span>
            <span suppressHydrationWarning>
              {formatPercek(osszPerc)}
              {showCost && osszKoltseg != null && (
                <span suppressHydrationWarning className="text-text-muted">
                  {" "}
                  · {formatFt(osszKoltseg)}
                </span>
              )}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
