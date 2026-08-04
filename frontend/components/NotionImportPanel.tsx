"use client";

import { useEffect, useRef, useState } from "react";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";

type ImportStatus = {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  log: string[];
};

const POLL_MS = 2000;

/** A Notion import elindítása/követése a böngészőből, `railway ssh` nélkül -
 * lásd backend/app/api/routes/admin_import.py: a háttérben futó import a
 * Railway-en éppen futó backend service saját processzében fut, ezért egy
 * bezárt böngészőlap/megszakadt kapcsolat nem szakítja félbe (csak egy
 * redeploy/újraindítás tenné). Admin-only - a backend 403-at ad nem-adminnak,
 * ezért ez a komponens csak akkor jelenik meg, ha a bejelentkezett
 * felhasználó admin (lásd Beállítások oldal). */
export function NotionImportPanel() {
  const confirm = useConfirm();
  const [status, setStatus] = useState<ImportStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchStatus() {
    const res = await authFetch("/api/v1/admin/notion-import/status");
    if (!res.ok) return;
    const body: ImportStatus = await res.json();
    setStatus(body);
    if (!body.running && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  useEffect(() => {
    fetchStatus();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (status?.running && !pollRef.current) {
      pollRef.current = setInterval(fetchStatus, POLL_MS);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.running]);

  async function start() {
    if (!(await confirm("Elindítja a teljes Notion importot (mind a 3 kör) - ez akár órákig is eltarthat a Notion API rate limitje miatt. Folytatod?"))) {
      return;
    }
    setStarting(true);
    setStartError(null);
    try {
      const res = await authFetch("/api/v1/admin/notion-import", { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setStartError(detail?.detail ?? `HTTP ${res.status}`);
        return;
      }
      await fetchStatus();
    } catch (err) {
      setStartError(`Hálózati hiba: ${err}`);
    } finally {
      setStarting(false);
    }
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <button
          type="button"
          onClick={start}
          disabled={starting || !!status?.running}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          {status?.running ? "Fut…" : "Notion import indítása"}
        </button>
        {status?.running && <span className="text-[12px] text-text-muted">Elindítva: {status.started_at}</span>}
      </div>
      <p className="mb-3 text-[12px] text-text-muted">
        Az import a Notionba FELTÖLTÖTT fájlokat (szerződések, TIG-ek, számlák) is áthozza, és a saját
        tárhelyünkre (R2) menti - a Notion linkjei ugyanis egy óra után lejárnak. A külső hivatkozások
        (pl. Google Docs) érintetlenül maradnak.
      </p>
      {startError && <p className="mb-3 text-[12px] text-text-danger">{startError}</p>}
      {status && !status.running && status.finished_at && (
        <p className="mb-2 text-[12px] text-text-muted">
          Utolsó futás vége: {status.finished_at}
          {status.error && <span className="text-text-danger"> - hiba: {status.error}</span>}
        </p>
      )}
      {status && status.log.length > 0 && (
        <pre className="max-h-72 overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-1 p-3 text-[11px] leading-relaxed whitespace-pre-wrap text-text-secondary">
          {status.log.join("\n")}
        </pre>
      )}
    </div>
  );
}
