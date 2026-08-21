"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { StatusBadge } from "@/components/StatusBadge";

type SyncStatusCalendar = { calendar_id: string; has_sync_token: boolean; last_synced_at: string | null };
type Connection = {
  connected: boolean;
  account_email: string | null;
  connected_at: string | null;
  /** Mikor újult meg utoljára a hozzáférés, és mi volt az utolsó hiba. A
   * tárolt token megléte önmagában nem bizonyítja, hogy ÉL a kapcsolat (lásd
   * backend services/google_oauth.load_credentials). */
  last_refresh_at?: string | null;
  last_error?: string | null;
  last_error_at?: string | null;
  client_configured: boolean;
  redirect_uri: string | null;
};
type SyncStatus = { connection: Connection; calendars: SyncStatusCalendar[] };
type SyncStats = {
  created: number;
  linked_existing: number;
  updated: number;
  deleted: number;
  skipped: number;
  full_resync: boolean;
  total_events: number;
};

/** A HYPE CALENDAR -> Projekt naptár-szinkron beállítása/állapota.
 *
 * A Google fiókot egyszer kell összekötni ("Csatlakozás Google fiókkal"),
 * onnantól a szinkron percenként magától fut (Celery Beat, lásd
 * backend/app/workers/calendar_tasks.py), és a hozzáférést a háttérben tárolt
 * refresh token újítja meg - adminnak nem kell token/JSON-t másolgatnia
 * környezeti változóba (lásd backend/app/services/google_oauth.py).
 *
 * A "Szinkronizálás most" gomb csak kényelmi/tesztelési célt szolgál: azonnal
 * visszajelez, anélkül hogy meg kellene várni a következő automatikus futást. */
export function CalendarSyncPanel() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [lastStats, setLastStats] = useState<SyncStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function refreshStatus() {
    const res = await authFetch("/api/v1/admin/calendar-sync/status");
    if (res.ok) setStatus(await res.json());
  }

  useEffect(() => {
    refreshStatus();
  }, []);

  // A Google a bejelentkezés után a backend callbackjére, az pedig ide, a
  // Beállítások oldalra irányít vissza, az eredményt query paraméterben hozva.
  // Ez SZÁRMAZTATOTT érték (a mindenkori URL-ből olvassuk), nem useEffect +
  // setState - így nincs felesleges újrarenderelés, és nem tud "beragadni" egy
  // korábbi állapot sem.
  const authResult = searchParams.get("calendar_auth");
  const authAccount = searchParams.get("account");
  const urlNotice =
    authResult === "ok"
      ? `Google fiók összekötve${authAccount ? `: ${authAccount}` : ""}. A szinkron mostantól magától fut.`
      : null;
  const urlError =
    authResult && authResult !== "ok"
      ? searchParams.get("message") || "Nem sikerült összekötni a Google fiókot."
      : null;

  async function connect() {
    setConnecting(true);
    setError(null);
    try {
      const res = await authFetch("/api/v1/admin/calendar-sync/oauth/start", { method: "POST" });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setError(data?.detail ?? `HTTP ${res.status}`);
        return;
      }
      // Teljes oldal-navigáció (nem router.push): a Google bejelentkezés egy
      // KÜLSŐ domain, amit a Next.js router nem tud kezelni.
      window.location.href = data.auth_url;
    } catch (err) {
      setError(`Hálózati hiba: ${err}`);
    } finally {
      setConnecting(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    setError(null);
    try {
      await authFetch("/api/v1/admin/calendar-sync/oauth/disconnect", { method: "POST" });
      setNotice(null);
      await refreshStatus();
    } finally {
      setBusy(false);
    }
  }

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

  const conn = status?.connection;

  return (
    <div>
      <div className="mb-4 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
        {conn?.connected ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <StatusBadge label="Összekötve" tone="success" />
            <span className="text-[13px] text-text-primary">{conn.account_email ?? "(ismeretlen fiók)"}</span>
            <button
              type="button"
              onClick={disconnect}
              disabled={busy}
              className="ml-auto rounded-[var(--radius)] border border-border px-3 py-1.5 text-[12px] text-text-secondary transition-colors hover:bg-bg-danger hover:text-text-danger disabled:opacity-50"
            >
              Kapcsolat bontása
            </button>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <StatusBadge label="Nincs összekötve" tone="neutral" />
            <span className="text-[13px] text-text-secondary">
              Kösd össze a Google fiókot, amelyik látja a HYPE CALENDAR naptárat - csak egyszer kell.
            </span>
            <button
              type="button"
              onClick={connect}
              disabled={connecting || !conn?.client_configured}
              className="btn btn-primary ml-auto"
            >
              {connecting ? "Átirányítás…" : "Csatlakozás Google fiókkal"}
            </button>
          </div>
        )}

        {/* ÉL-E a kapcsolat. A hozzáférés magától megújul, amíg a Google
            engedi - ha mégsem, itt látszik, mióta és miért. A leggyakoribb ok
            nem nálunk van: „Testing” állapotú Google Cloud projektnél a Google
            7 naponta érvényteleníti a hozzáférést. */}
        {conn?.connected && conn.last_error && (
          <p className="mt-2 text-[12px] text-text-warning">
            A hozzáférés megújítása nem sikerült
            {conn.last_error_at ? ` (${new Date(conn.last_error_at).toLocaleString("hu-HU")})` : ""}:{" "}
            {conn.last_error}
          </p>
        )}
        {conn?.connected && !conn.last_error && conn.last_refresh_at && (
          <p className="mt-2 text-[11px] text-text-muted">
            A hozzáférés magától megújul – utoljára: {new Date(conn.last_refresh_at).toLocaleString("hu-HU")}.
          </p>
        )}

        {conn && !conn.client_configured && (
          <p className="mt-2 text-[12px] text-text-warning">
            Nincs Google OAuth kliens beállítva a backenden, ezért a csatlakozás gomb nem használható. Hozz létre egy
            &quot;OAuth client ID / Web application&quot; klienst a Google Cloud Console-ban, és add meg a
            GOOGLE_CALENDAR_OAUTH_CLIENT_ID / GOOGLE_CALENDAR_OAUTH_CLIENT_SECRET változókat (ha a Gmail
            integrációhoz már van kliensed, azt is használhatod).
          </p>
        )}
        {conn?.redirect_uri ? (
          <p className="mt-2 break-all text-[11px] text-text-muted">
            Engedélyezett átirányítási cím – ezt másold be a Google Cloud Console &quot;Authorized redirect URIs&quot;
            mezőjébe, pontosan így:{" "}
            <code className="rounded bg-surface-2 px-1 py-0.5 text-text-secondary">{conn.redirect_uri}</code>
          </p>
        ) : (
          <p className="mt-2 text-[11px] text-text-warning">
            Nincs beállítva az API_BASE_URL környezeti változó a backenden, ezért nem tudjuk kiírni a Google Cloud
            Console-ba beírandó átirányítási címet. Állítsd be a backend nyilvános címére (ugyanaz, amit a frontend
            NEXT_PUBLIC_API_URL-ként használ, pl. https://hype-os-backend.up.railway.app).
          </p>
        )}
      </div>

      <div className="mb-3 flex items-center gap-3">
        <button
          type="button"
          onClick={triggerSync}
          disabled={busy || !conn?.connected}
          className="btn btn-ghost"
        >
          {busy ? "Szinkronizálás…" : "Szinkronizálás most"}
        </button>
      </div>

      {(notice ?? urlNotice) && <p className="mb-3 text-[12px] text-text-success">{notice ?? urlNotice}</p>}
      {(error ?? urlError) && <p className="mb-3 text-[12px] text-text-danger">{error ?? urlError}</p>}
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
