"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/authFetch";
import { StatusBadge } from "@/components/StatusBadge";

type SyncStatusCalendar = { calendar_id: string; has_sync_token: boolean; last_synced_at: string | null };
type SyncStatus = { calendars: SyncStatusCalendar[] };
type SyncStats = {
  created: number;
  linked_existing: number;
  updated: number;
  deleted: number;
  skipped: number;
  full_resync: boolean;
  total_events: number;
};

/** A HYPE CALENDAR -> Projekt naptár-szinkron kézi indítása/állapota - a
 * tényleges szinkron percenként automatikusan lefut (Celery Beat, lásd
 * backend/app/workers/calendar_tasks.py), ez a panel csak azért kell, hogy
 * admin láthassa, be van-e állítva a hitelesítés, mikor futott utoljára, és
 * hogy azonnal tesztelhesse anélkül, hogy megvárná a következő automatikus
 * futást. */
export function CalendarSyncPanel() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [lastStats, setLastStats] = useState<SyncStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refreshStatus() {
    const res = await authFetch("/api/v1/admin/calendar-sync/status");
    if (res.ok) setStatus(await res.json());
  }

  useEffect(() => {
    refreshStatus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function triggerSync() {
    setBusy(true);
    setError(null);
    setLastStats(null);
    try {
      const res = await authFetch("/api/v1/admin/calendar-sync", { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setError(detail?.detail ?? `HTTP ${res.status}`);
        return;
      }
      setLastStats(await res.json());
      await refreshStatus();
    } catch (err) {
      setError(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <button
          type="button"
          onClick={triggerSync}
          disabled={busy}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          {busy ? "Szinkronizálás…" : "Szinkronizálás most"}
        </button>
      </div>
      {error && <p className="mb-3 text-[12px] text-text-danger">{error}</p>}
      {lastStats && (
        <p className="mb-3 text-[12px] text-text-secondary">
          {lastStats.created} új · {lastStats.linked_existing} összepárosítva (Notionból már megvolt) · {lastStats.updated} frissítve ·{" "}
          {lastStats.deleted} törölve · {lastStats.skipped} kihagyva
          {lastStats.full_resync ? " (teljes újraszinkron)" : ""}
        </p>
      )}
      {status && status.calendars.length === 0 ? (
        <p className="text-[12px] text-text-muted">Még nem futott le szinkron - nincs beállított naptár-állapot.</p>
      ) : (
        status?.calendars.map((c) => (
          <div key={c.calendar_id} className="flex items-center gap-2 text-[12px] text-text-secondary">
            <span className="min-w-0 flex-1 truncate">{c.calendar_id}</span>
            {c.has_sync_token ? <StatusBadge label="Aktív" tone="success" /> : <StatusBadge label="Nincs token" tone="neutral" />}
            {c.last_synced_at && <span className="text-text-muted">utoljára: {new Date(c.last_synced_at).toLocaleString("hu-HU")}</span>}
          </div>
        ))
      )}
    </div>
  );
}
