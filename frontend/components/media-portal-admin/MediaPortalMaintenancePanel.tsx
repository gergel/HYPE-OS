"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type PendingDeletion = {
  id: number;
  title: string;
  client_name: string;
  expires_at: string;
  video_count: number;
  image_count: number;
};

/** Nem portál-specifikus admin műveletek: Notion szinkron (külön Notion
 * adatbázis a portál-projektekhez, lásd services/portal_notion.py) és a
 * 90+ napja lejárt fizetős portálok fájljainak törlése (lásd
 * portal_admin.py maintenance végpontjai). */
export function MediaPortalMaintenancePanel() {
  const router = useRouter();
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingDeletion[] | null>(null);
  const [loadingPending, setLoadingPending] = useState(false);

  async function syncNotion() {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await authFetch("/api/v1/portal-admin/notion/sync", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? String(res.status));
      setSyncResult(
        data.error ? data.error : `Szinkronizálva: ${data.synced} (ebből új: ${data.created ?? 0}, kihagyva: ${data.skipped ?? 0})`,
      );
      router.refresh();
    } catch (err) {
      setSyncResult(`Hiba: ${err}`);
    } finally {
      setSyncing(false);
    }
  }

  async function loadPending() {
    setLoadingPending(true);
    try {
      const res = await authFetch("/api/v1/portal-admin/maintenance/pending-deletion");
      if (res.ok) setPending(await res.json());
    } finally {
      setLoadingPending(false);
    }
  }

  async function purge(portalId: number) {
    if (!confirm("Biztosan törlöd ennek a portálnak MINDEN videóját/fotóját? Ez nem vonható vissza.")) return;
    const res = await authFetch(`/api/v1/portal-admin/maintenance/${portalId}/purge-files`, { method: "POST" });
    if (res.ok) setPending((prev) => prev?.filter((p) => p.id !== portalId) ?? null);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={syncNotion}
          disabled={syncing}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          {syncing ? "Szinkronizálás…" : "Notion szinkron"}
        </button>
        {syncResult && <span className="text-[13px] text-text-muted">{syncResult}</span>}
      </div>

      <div>
        <button
          type="button"
          onClick={loadPending}
          disabled={loadingPending}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          {loadingPending ? "Betöltés…" : "Lejárt (90+ napja) fizetős portálok listázása"}
        </button>
        {pending && (
          <ul className="mt-3 space-y-2">
            {pending.length === 0 && <li className="text-[13px] text-text-muted">Nincs törlendő anyag.</li>}
            {pending.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center gap-3 rounded-[var(--radius)] bg-surface-1 p-2 text-[13px]">
                <span className="font-medium text-text-primary">{p.title}</span>
                <span className="text-text-muted">{p.client_name}</span>
                <span className="text-text-muted">lejárt: {p.expires_at.slice(0, 10)}</span>
                <span className="text-text-muted">
                  {p.video_count} videó, {p.image_count} kép
                </span>
                <button type="button" onClick={() => purge(p.id)} className="ml-auto text-text-danger hover:underline">
                  Fájlok törlése
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
