"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, ExternalLink, Lock, Plus, Trash2, Video } from "lucide-react";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import {
  createPortal,
  createManualPortal,
  deletePortal,
  getPendingDeletion,
  listPortals,
  purgePortalFiles,
  PendingDeletionPortal,
} from "@/lib/portalAdminApi";
import { useLiveTopic } from "@/lib/live";
import type { PortalSummary, Project } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";

const inputClass =
  "w-full min-w-0 flex-1 rounded-[var(--radius)] border border-border bg-surface-3 px-3.5 py-2.5 text-[13px] text-text-primary outline-none focus:border-text-accent/40 sm:w-auto";

/** A Média Portál admin dashboardja - a megosztott (lila akcentusú, sötét)
 * design rendszerre igazítva (Card/StatusBadge/lucide ikonok), a korábbi
 * különálló "ink/bone/mist/ember" vizuális nyelv helyett - a funkcionalitás
 * (projekt/kézi létrehozás, keresés/rendezés, törlésre váró anyagok purge-je)
 * változatlan. "Új Portál" alapból egy MEGLÉVŐ HYPE OS Project kiválasztását
 * jelenti (mert a Portal alapesetben 1:1 egy valódi Projekthez van kötve), de
 * a "Kézzel" fül lehetővé teszi Projekt nélküli, szabadon kitöltött cím/
 * ügyfélnév/dátum megadását is - ilyenkor a Portal project_id nélkül jön
 * létre, és a title_override/client_name_override/project_date_override
 * mezői adják az adatot. */
export function MediaPortalDashboard({
  initialPortals,
  availableProjects,
}: {
  initialPortals: PortalSummary[];
  availableProjects: Project[];
}) {
  const [projects, setProjects] = useState(initialPortals);
  const [pending, setPending] = useState<PendingDeletionPortal[]>([]);
  const [creating, setCreating] = useState(false);
  const [createMode, setCreateMode] = useState<"project" | "manual">("project");
  const [selectedProjectId, setSelectedProjectId] = useState<number | "">("");
  const [manualTitle, setManualTitle] = useState("");
  const [manualClientName, setManualClientName] = useState("");
  const [manualDate, setManualDate] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"date_desc" | "date_asc" | "name">("date_desc");
  const [confirmDelete, setConfirmDelete] = useState<{ id: number; title: string } | null>(null);
  const [confirmPurge, setConfirmPurge] = useState<{ id: number; title: string } | null>(null);
  const [purging, setPurging] = useState(false);

  // Ha valaki más hoz létre/töröl portált, itt is látszódjon újratöltés nélkül.
  useLiveTopic("portals", () => {
    void refresh();
  });

  async function refresh() {
    setProjects(await listPortals());
  }
  async function refreshPending() {
    try {
      setPending(await getPendingDeletion());
    } catch {
      setPending([]);
    }
  }
  useEffect(() => {
    refreshPending();
  }, []);

  async function doCreate() {
    try {
      const created =
        createMode === "project"
          ? selectedProjectId
            ? await createPortal(selectedProjectId)
            : null
          : manualTitle.trim()
            ? await createManualPortal(manualTitle.trim(), manualClientName.trim(), manualDate.trim())
            : null;
      if (!created) return;
      setSelectedProjectId("");
      setManualTitle("");
      setManualClientName("");
      setManualDate("");
      setCreating(false);
      refresh();
      window.location.href = `/media-portal/${created.id}`;
    } catch (err) {
      alert(`Portál létrehozása sikertelen: ${err instanceof Error ? err.message : err}`);
    }
  }

  function onDelete(e: React.MouseEvent, id: number, title: string) {
    e.preventDefault();
    e.stopPropagation();
    setConfirmDelete({ id, title });
  }

  async function doDelete() {
    if (!confirmDelete) return;
    try {
      await deletePortal(confirmDelete.id);
      setConfirmDelete(null);
      refresh();
      refreshPending();
    } catch (err) {
      alert(`Portál törlése sikertelen: ${err instanceof Error ? err.message : err}`);
    }
  }

  async function doPurge() {
    if (!confirmPurge) return;
    setPurging(true);
    try {
      await purgePortalFiles(confirmPurge.id);
      setConfirmPurge(null);
      refreshPending();
    } catch (err) {
      alert(`Fájlok törlése sikertelen: ${err instanceof Error ? err.message : err}`);
    } finally {
      setPurging(false);
    }
  }

  const visibleProjects = projects
    .filter((p) => {
      const q = search.toLowerCase();
      return (
        p.title.toLowerCase().includes(q) ||
        p.client_name.toLowerCase().includes(q) ||
        (p.project_date || "").toLowerCase().includes(q)
      );
    })
    .sort((a, b) => {
      if (sortBy === "name") return a.title.localeCompare(b.title);
      const da = a.project_date || "";
      const db = b.project_date || "";
      if (sortBy === "date_asc") return da.localeCompare(db);
      return db.localeCompare(da);
    });

  return (
    <div className="flex-1 space-y-6 p-6 lg:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide text-text-muted">HYPE Productions</p>
          <h1 className="mt-1 text-2xl font-semibold text-text-primary">Portálok</h1>
        </div>
        <button
          type="button"
          onClick={() => setCreating((v) => !v)}
          className="flex items-center gap-1.5 rounded-[var(--radius)] px-4 py-2 text-[13px] font-medium text-white shadow-[0_4px_14px_-4px_rgba(124,92,255,0.55)]"
          style={{ background: "var(--accent-gradient)" }}
        >
          <Plus className="h-4 w-4" />
          Új Portál
        </button>
      </div>

      {pending.length > 0 && (
        <Card>
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 shrink-0 text-text-danger" />
            <h2 className="text-[15px] font-medium text-text-primary">Törlésre váró anyagok</h2>
          </div>
          <p className="mt-1.5 text-[13px] text-text-secondary">
            Ezek a fizetős portálok több mint 90 napja lejártak. Az anyagok törölhetők az R2 tárhelyből. A projekt
            megmarad, a kapcsolatfelvételi oldal továbbra is működik.
          </p>
          <ul className="mt-4 space-y-2">
            {pending.map((p) => (
              <li
                key={p.id}
                className="flex flex-col gap-3 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="truncate text-[13px] text-text-primary">{p.title}</p>
                  <p className="truncate text-[11px] text-text-muted">
                    {p.client_name || "—"} · {p.video_count} videó · {p.image_count} kép · lejárt: {p.expires_at.slice(0, 10)}
                  </p>
                </div>
                <button
                  onClick={() => setConfirmPurge({ id: p.id, title: p.title })}
                  className="flex shrink-0 items-center justify-center gap-2 rounded-[var(--radius)] border border-text-danger/40 px-3.5 py-1.5 text-[13px] text-text-danger transition-colors hover:bg-bg-danger"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Fájlok törlése
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {creating && (
        <Card>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setCreateMode("project")}
              className={`rounded-full px-4 py-1.5 text-[13px] transition-colors ${
                createMode === "project"
                  ? "text-white"
                  : "border border-border text-text-secondary hover:text-text-primary"
              }`}
              style={createMode === "project" ? { background: "var(--accent-gradient)" } : undefined}
            >
              Meglévő projekt
            </button>
            <button
              type="button"
              onClick={() => setCreateMode("manual")}
              className={`rounded-full px-4 py-1.5 text-[13px] transition-colors ${
                createMode === "manual"
                  ? "text-white"
                  : "border border-border text-text-secondary hover:text-text-primary"
              }`}
              style={createMode === "manual" ? { background: "var(--accent-gradient)" } : undefined}
            >
              Kézzel
            </button>
          </div>

          {createMode === "project" ? (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <KeresosSelect
                value={selectedProjectId === "" ? null : String(selectedProjectId)}
                options={availableProjects.map((p) => ({ value: String(p.id), label: p.nev }))}
                onChange={(ertek) => setSelectedProjectId(Number(ertek))}
                placeholder="Válassz projektet…"
                className="min-w-[240px]"
              />
              <button
                type="button"
                onClick={doCreate}
                disabled={!selectedProjectId}
                className="w-full shrink-0 rounded-[var(--radius)] px-4 py-2.5 text-[13px] font-medium text-white disabled:opacity-40 sm:w-auto"
                style={{ background: "var(--accent-gradient)" }}
              >
                Létrehozás
              </button>
            </div>
          ) : (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <input
                placeholder="Portál címe (kötelező)…"
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
                className={inputClass}
              />
              <input
                placeholder="Ügyfél neve…"
                value={manualClientName}
                onChange={(e) => setManualClientName(e.target.value)}
                className={inputClass}
              />
              <input
                placeholder="Dátum (pl. 2026.06.17)…"
                value={manualDate}
                onChange={(e) => setManualDate(e.target.value)}
                className={inputClass}
              />
              <button
                type="button"
                onClick={doCreate}
                disabled={!manualTitle.trim()}
                className="w-full shrink-0 rounded-[var(--radius)] px-4 py-2.5 text-[13px] font-medium text-white disabled:opacity-40 sm:w-auto"
                style={{ background: "var(--accent-gradient)" }}
              >
                Létrehozás
              </button>
            </div>
          )}
        </Card>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <input
          placeholder="Keresés: projekt, ügyfél vagy dátum…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className={inputClass}
        />
        <KeresosSelect
          value={sortBy}
          options={[
            { value: "date_desc", label: "Dátum (legújabb elöl)" },
            { value: "date_asc", label: "Dátum (legrégebbi elöl)" },
            { value: "name", label: "Név (A–Z)" },
          ]}
          onChange={(ertek) => setSortBy(ertek as typeof sortBy)}
          className="w-[220px]"
        />
      </div>

      <div className="overflow-hidden rounded-[var(--radius-lg)] border border-border">
        {visibleProjects.length === 0 && (
          <p className="bg-surface-2 p-8 text-center text-[13px] text-text-muted">
            {projects.length === 0 ? "Még nincs Portál. Hozz létre egyet a kezdéshez." : "Nincs találat a keresésre."}
          </p>
        )}
        <div className="divide-y divide-border">
          {visibleProjects.map((p) => (
            <a
              key={p.id}
              href={`/media-portal/${p.id}`}
              className="flex items-center gap-4 bg-surface-2 px-5 py-4 transition-colors hover:bg-surface-3"
            >
              <div className="flex h-12 w-20 shrink-0 items-center justify-center overflow-hidden rounded-[var(--radius)] bg-surface-3">
                {p.cover_image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={p.cover_image_url} alt="" className="h-full w-full object-cover" />
                ) : (
                  <Video className="h-4 w-4 text-text-muted" aria-hidden />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="truncate text-[15px] font-medium text-text-primary">{p.title}</h3>
                <p className="truncate text-[13px] text-text-secondary">
                  {p.client_name}
                  {p.project_date ? ` · ${p.project_date}` : ""}
                </p>
              </div>
              <StatusBadge label={p.status === "live" ? "Élő" : p.status} tone={p.status === "live" ? "success" : "neutral"} />
              {p.has_password && <Lock className="h-3.5 w-3.5 shrink-0 text-text-accent" aria-hidden />}
              <ExternalLink className="h-4 w-4 shrink-0 text-text-muted" aria-hidden />
              <button
                onClick={(e) => onDelete(e, p.id, p.title)}
                title="Portál törlése"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-text-muted transition-colors hover:bg-bg-danger hover:text-text-danger"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </a>
          ))}
        </div>
      </div>

      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={() => setConfirmDelete(null)}>
          <div
            className="w-full max-w-sm rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-[13px] leading-relaxed text-text-primary">
              Biztosan törlöd a(z) &ldquo;{confirmDelete.title}&rdquo; Portált az összes videójával és képével együtt? Ez
              nem vonható vissza.
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmDelete(null)}
                className="rounded-[var(--radius)] border border-border px-4 py-2 text-[13px] text-text-secondary hover:bg-surface-3"
              >
                Mégse
              </button>
              <button
                onClick={doDelete}
                className="flex items-center gap-2 rounded-[var(--radius)] border border-text-danger/40 px-4 py-2 text-[13px] text-text-danger transition-colors hover:bg-bg-danger"
              >
                Törlés
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmPurge && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6"
          onClick={() => !purging && setConfirmPurge(null)}
        >
          <div
            className="w-full max-w-sm rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-[13px] leading-relaxed text-text-primary">
              Törlöd a(z) &ldquo;{confirmPurge.title}&rdquo; Portál összes fájlját (videók és képek) az R2 tárhelyből? A
              projekt megmarad, a kapcsolatfelvételi oldal továbbra is működik. Ez a művelet nem vonható vissza.
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmPurge(null)}
                disabled={purging}
                className="rounded-[var(--radius)] border border-border px-4 py-2 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Mégse
              </button>
              <button
                onClick={doPurge}
                disabled={purging}
                className="flex items-center gap-2 rounded-[var(--radius)] border border-text-danger/40 px-4 py-2 text-[13px] text-text-danger transition-colors hover:bg-bg-danger disabled:opacity-60"
              >
                <Trash2 className="h-4 w-4" />
                {purging ? "Törlés…" : "Fájlok törlése"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
