"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  createDownloadUrl,
  createGalleryExport,
  formatBytes,
  getGalleryExport,
  getGalleryExportState,
  type DownloadTicket,
  type ExportStatus,
  type GalleryExport,
  type GalleryExportState,
  type GalleryPlan,
} from "@/lib/api";

const POLL_MS = 2000;

const STATUS_LABEL: Record<ExportStatus, string> = {
  queued: "Várakozó",
  running: "Készülő",
  ready: "Kész",
  failed: "Hibás",
  expired: "Lejárt",
};

const STATUS_CLASS: Record<ExportStatus, string> = {
  queued: "bg-surface-2 text-text-secondary",
  running: "bg-bg-accent text-text-accent",
  ready: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-red-500/15 text-red-300",
  expired: "bg-amber-500/15 text-amber-300",
};

const ERROR_LABEL: Record<string, string> = {
  source_missing: "Egy forrásfájl hiányzik a tárból.",
  source_changed: "A galéria a csomagolás közben megváltozott - kérj új exportot.",
  storage_error: "Tárhiba történt a csomagolás közben.",
  stale_timeout: "A feldolgozás megszakadt (worker leállt).",
  empty_gallery: "A galéria üres.",
  too_many_files: "Túl sok fájl van a galériában.",
};

type Props = { projectId: number };

export function GalleryExportPanel({ projectId }: Props) {
  const [plan, setPlan] = useState<GalleryPlan | null>(null);
  const [job, setJob] = useState<GalleryExport | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const [ticket, setTicket] = useState<DownloadTicket | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const busyRef = useRef(false);

  // Oldalbetöltéskor (újranyitás után is) a szerverről kérjük az aktuális jobot.
  const applyState = useCallback((state: GalleryExportState) => {
    setPlan(state.plan);
    setJob(state.job);
    setUnavailable(state.unavailable_reason);
    setError(null);
  }, []);

  const loadState = useCallback(async () => {
    try {
      applyState(await getGalleryExportState(projectId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nem sikerült elérni a backend API-t.");
    } finally {
      setLoaded(true);
    }
  }, [projectId, applyState]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const state = await getGalleryExportState(projectId);
        if (!cancelled) applyState(state);
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Nem sikerült elérni a backend API-t.");
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, applyState]);

  // Valós előrehaladás: amíg a job várakozó/készülő, 2 mp-enként frissítünk.
  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "running")) return;
    const timer = window.setInterval(async () => {
      try {
        setJob(await getGalleryExport(job.public_id));
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) setJob(null);
      }
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [job]);

  async function handleCreate() {
    // Dupla kattintás elleni védelem kliensoldalon is (a szerver amúgy is idempotens).
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    setTicket(null);
    try {
      setJob(await createGalleryExport(projectId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Nem sikerült elindítani az exportot.");
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  async function handleDownload() {
    if (!job) return;
    setError(null);
    try {
      const fresh = await createDownloadUrl(job.public_id);
      setTicket(fresh);
      window.location.assign(fresh.url);
    } catch (err) {
      if (err instanceof ApiError && err.status === 410) {
        setTicket(null);
        await loadState();
      }
      setError(err instanceof ApiError ? err.message : "Nem sikerült letöltési linket kérni.");
    }
  }

  const status = job?.status ?? null;
  const percent = job ? Math.max(0, Math.min(100, job.progress_percent)) : 0;
  const isActive = status === "queued" || status === "running";
  const canCreate = !!plan && !isActive && status !== "ready";

  return (
    <section
      data-testid="gallery-export-panel"
      className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-5"
    >
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-text-primary">Teljes galéria letöltése (ZIP)</p>
          <p className="text-[12px] text-text-secondary">
            A csomagot háttérfeladat készíti el a szerveren; az oldal bezárása után is folytatódik.
          </p>
        </div>
        {status && (
          <span
            data-testid="export-status"
            data-status={status}
            className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${STATUS_CLASS[status]}`}
          >
            {STATUS_LABEL[status]}
          </span>
        )}
      </div>

      {!loaded && <p className="text-[13px] text-text-muted">Betöltés...</p>}

      {loaded && unavailable && !job && (
        <p className="text-[13px] text-text-muted" data-testid="export-unavailable">
          {unavailable}
        </p>
      )}

      {plan && (
        <p className="mb-3 text-[12px] text-text-muted" data-testid="export-plan">
          {plan.file_count} fájl · {formatBytes(plan.total_source_bytes)} forrás · várható csomag{" "}
          {formatBytes(plan.expected_archive_bytes)}
        </p>
      )}

      {job && (
        <div className="mb-3">
          <div className="mb-1 flex justify-between text-[12px] text-text-secondary">
            <span data-testid="export-progress-text">
              {job.files_done}/{job.file_count} fájl · {formatBytes(job.bytes_done)} /{" "}
              {formatBytes(job.total_source_bytes)}
            </span>
            <span data-testid="export-percent">{percent.toFixed(0)}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface-1">
            <div
              data-testid="export-progress-bar"
              className={`h-full rounded-full transition-[width] ${
                status === "failed" ? "bg-red-400" : status === "expired" ? "bg-amber-400" : "bg-text-accent"
              }`}
              style={{ width: `${percent}%` }}
            />
          </div>
          {status === "failed" && (
            <p className="mt-2 text-[12px] text-red-300" data-testid="export-error">
              {(job.error_code && ERROR_LABEL[job.error_code]) || job.error_message || "Ismeretlen hiba."}{" "}
              ({job.attempts}/{job.max_attempts} próbálkozás)
            </p>
          )}
          {status === "expired" && (
            <p className="mt-2 text-[12px] text-amber-300">
              A csomag lejárt és törlődött. Kérj újat - az eredeti fájlok érintetlenek.
            </p>
          )}
          {status === "ready" && (
            <p className="mt-2 text-[12px] text-text-muted" data-testid="export-ready-meta">
              {job.filename} · {formatBytes(job.object_size ?? 0)}
              {job.expires_at && ` · elérhető eddig: ${new Date(job.expires_at).toLocaleString("hu-HU")}`}
            </p>
          )}
        </div>
      )}

      {error && (
        <p className="mb-3 text-[13px] text-text-danger" data-testid="export-api-error">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {canCreate && (
          <button
            type="button"
            data-testid="export-create"
            onClick={handleCreate}
            disabled={busy}
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-2 text-[13px] font-medium text-text-accent disabled:opacity-50"
          >
            {status === "failed" || status === "expired" ? "Új csomag kérése" : "Csomag elkészítése"}
          </button>
        )}
        {status === "ready" && (
          <button
            type="button"
            data-testid="export-download"
            onClick={handleDownload}
            className="rounded-[var(--radius)] bg-bg-accent px-3 py-2 text-[13px] font-medium text-text-accent"
          >
            Letöltés
          </button>
        )}
        {isActive && (
          <button
            type="button"
            disabled
            data-testid="export-pending"
            className="rounded-[var(--radius)] border border-border px-3 py-2 text-[13px] text-text-secondary opacity-70"
          >
            {status === "queued" ? "Sorban áll..." : "Csomagolás folyamatban..."}
          </button>
        )}
      </div>

      {ticket && (
        <p className="mt-3 break-all text-[11px] text-text-muted" data-testid="export-ticket">
          Link érvényes eddig: {new Date(ticket.expires_at).toLocaleTimeString("hu-HU")} · ha lejár, kattints újra a
          Letöltésre - ugyanaz a csomag folytatható (ETag {ticket.etag.slice(0, 12)}…).
        </p>
      )}
    </section>
  );
}
