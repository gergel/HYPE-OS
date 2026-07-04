"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
export function TimerControls({ deliverableId, initialState }: { deliverableId: number; initialState: TimerState | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(() => new Date());
  const running = Boolean(initialState?.my_running_since);

  useEffect(() => {
    if (!running) return;
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  }, [running]);

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
        {running && initialState?.my_running_since && (
          <span className="text-[13px] tabular-nums text-text-secondary">
            {formatElapsedSince(initialState.my_running_since, now)}
          </span>
        )}
      </div>

      {initialState && initialState.by_employee.length > 0 && (
        <div className="space-y-1">
          {initialState.by_employee.map((e) => (
            <div key={e.employee_id} className="flex items-center justify-between text-[12px] text-text-secondary">
              <span>{e.full_name}</span>
              <span>
                {formatMinutes(e.total_minutes)}
                {e.total_cost != null && <span className="text-text-muted"> · {Math.round(e.total_cost)} Ft</span>}
              </span>
            </div>
          ))}
          <div className="mt-1.5 flex items-center justify-between border-t border-border pt-1.5 text-[12px] font-medium text-text-primary">
            <span>Összesen</span>
            <span>
              {formatMinutes(initialState.total_minutes)}
              {initialState.total_cost != null && <span className="text-text-muted"> · {Math.round(initialState.total_cost)} Ft</span>}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
