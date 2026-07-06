"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Plus, ExternalLink, Trash2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/media-portal/ui/button";
import {
  createPortal,
  createManualPortal,
  deletePortal,
  getPendingDeletion,
  listPortals,
  purgePortalFiles,
  PendingDeletionPortal,
} from "@/lib/portalAdminApi";
import type { PortalSummary, Project } from "@/lib/api";

/** A Média Portál admin dashboardja - a Hype-repo-main (különálló
 * client-portál projekt) admin/page.tsx Dashboard komponensének 1:1
 * vizuális portja. "Új Portál" alapból egy MEGLÉVŐ HYPE OS Project
 * kiválasztását jelenti (mert a Portal alapesetben 1:1 egy valódi
 * Projekthez van kötve), de a "Kézzel" fül lehetővé teszi Projekt
 * nélküli, szabadon kitöltött cím/ügyfélnév/dátum megadását is - ilyenkor
 * a Portal project_id nélkül jön létre, és a title_override/
 * client_name_override/project_date_override mezői adják az adatot. */
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
    <main className="hype-portal dark mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-16">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-eyebrow text-mist">HYPE Productions</p>
          <h1 className="mt-1 font-display text-3xl text-bone">Portálok</h1>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button variant="ember" onClick={() => setCreating((v) => !v)}>
            <Plus className="h-4 w-4" />
            Új Portál
          </Button>
        </div>
      </div>

      {pending.length > 0 && (
        <div className="mt-6 rounded-2xl border border-ember/40 bg-ember/[0.06] p-4 sm:p-5">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 shrink-0 text-ember" />
            <h2 className="font-display text-lg text-bone">Törlésre váró anyagok</h2>
          </div>
          <p className="mt-1.5 text-sm text-mist">
            Ezek a fizetős portálok több mint 90 napja lejártak. Az anyagok törölhetők az R2 tárhelyből. A projekt
            megmarad, a kapcsolatfelvételi oldal továbbra is működik.
          </p>
          <ul className="mt-4 space-y-2">
            {pending.map((p) => (
              <li
                key={p.id}
                className="flex flex-col gap-3 rounded-xl border border-ink-line bg-ink px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm text-bone">{p.title}</p>
                  <p className="truncate font-mono text-[11px] text-mist">
                    {p.client_name || "—"} · {p.video_count} videó · {p.image_count} kép · lejárt: {p.expires_at.slice(0, 10)}
                  </p>
                </div>
                <button
                  onClick={() => setConfirmPurge({ id: p.id, title: p.title })}
                  className="flex shrink-0 items-center justify-center gap-2 rounded-full border border-ember/50 px-4 py-2 text-sm text-ember transition hover:bg-ember/10"
                >
                  <Trash2 className="h-4 w-4" />
                  Fájlok törlése
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {creating && (
        <div className="mt-6 rounded-2xl border border-ink-line bg-ink-card p-4">
          <div className="flex gap-2">
            <button
              onClick={() => setCreateMode("project")}
              className={`rounded-full px-4 py-1.5 text-sm transition ${
                createMode === "project" ? "bg-ember text-ink" : "border border-ink-line text-mist hover:text-bone"
              }`}
            >
              Meglévő projekt
            </button>
            <button
              onClick={() => setCreateMode("manual")}
              className={`rounded-full px-4 py-1.5 text-sm transition ${
                createMode === "manual" ? "bg-ember text-ink" : "border border-ink-line text-mist hover:text-bone"
              }`}
            >
              Kézzel
            </button>
          </div>

          {createMode === "project" ? (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <select
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value ? Number(e.target.value) : "")}
                className="w-full min-w-0 flex-1 rounded-full border border-ink-line bg-ink px-4 py-2.5 text-bone outline-none focus:border-ember/60 sm:w-auto"
              >
                <option value="">Válassz projektet…</option>
                {availableProjects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nev}
                  </option>
                ))}
              </select>
              <Button variant="primary" onClick={doCreate} disabled={!selectedProjectId} className="w-full sm:w-auto">
                Létrehozás
              </Button>
            </div>
          ) : (
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <input
                placeholder="Portál címe (kötelező)…"
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
                className="w-full min-w-0 flex-1 rounded-full border border-ink-line bg-ink px-4 py-2.5 text-bone outline-none focus:border-ember/60 sm:w-auto"
              />
              <input
                placeholder="Ügyfél neve…"
                value={manualClientName}
                onChange={(e) => setManualClientName(e.target.value)}
                className="w-full min-w-0 flex-1 rounded-full border border-ink-line bg-ink px-4 py-2.5 text-bone outline-none focus:border-ember/60 sm:w-auto"
              />
              <input
                placeholder="Dátum (pl. 2026.06.17)…"
                value={manualDate}
                onChange={(e) => setManualDate(e.target.value)}
                className="w-full min-w-0 flex-1 rounded-full border border-ink-line bg-ink px-4 py-2.5 text-bone outline-none focus:border-ember/60 sm:w-auto"
              />
              <Button variant="primary" onClick={doCreate} disabled={!manualTitle.trim()} className="w-full sm:w-auto">
                Létrehozás
              </Button>
            </div>
          )}
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <input
          placeholder="Keresés: projekt, ügyfél vagy dátum…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full min-w-0 flex-1 rounded-full border border-ink-line bg-ink px-4 py-2.5 text-bone outline-none focus:border-ember/60 sm:w-auto"
        />
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          className="w-full rounded-full border border-ink-line bg-ink px-4 py-2.5 text-bone outline-none focus:border-ember/60 sm:w-auto"
        >
          <option value="date_desc">Dátum (legújabb elöl)</option>
          <option value="date_asc">Dátum (legrégebbi elöl)</option>
          <option value="name">Név (A–Z)</option>
        </select>
      </div>

      <div className="mt-6 divide-y divide-ink-line overflow-hidden rounded-2xl border border-ink-line">
        {visibleProjects.length === 0 && (
          <p className="p-8 text-center text-mist">
            {projects.length === 0 ? "Még nincs Portál. Hozz létre egyet a kezdéshez." : "Nincs találat a keresésre."}
          </p>
        )}
        {visibleProjects.map((p) => (
          <a
            key={p.id}
            href={`/media-portal/${p.id}`}
            className="flex items-center gap-4 bg-ink-card px-5 py-4 transition hover:bg-white/[0.03]"
          >
            <div className="h-12 w-20 shrink-0 overflow-hidden rounded-lg bg-ink-soft">
              {p.cover_image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={p.cover_image_url} alt="" className="h-full w-full object-cover" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="truncate font-display text-lg text-bone">{p.title}</h3>
              <p className="truncate text-sm text-mist">
                {p.client_name}
                {p.project_date ? ` · ${p.project_date}` : ""}
              </p>
            </div>
            <span className="font-mono text-[11px] uppercase tracking-eyebrow text-mist">{p.status}</span>
            {p.has_password && (
              <span className="font-mono text-[11px] uppercase tracking-eyebrow text-ember">zárolt</span>
            )}
            <ExternalLink className="h-4 w-4 text-mist" />
            <button
              onClick={(e) => onDelete(e, p.id, p.title)}
              title="Portál törlése"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-mist transition hover:bg-ember/10 hover:text-ember"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </a>
        ))}
      </div>

      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={() => setConfirmDelete(null)}>
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full max-w-sm rounded-2xl border border-ink-line bg-ink-card p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm leading-relaxed text-bone">
              Biztosan törlöd a(z) &ldquo;{confirmDelete.title}&rdquo; Portált az összes videójával és képével együtt? Ez
              nem vonható vissza.
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(null)}>
                Mégse
              </Button>
              <button
                onClick={doDelete}
                className="flex items-center gap-2 rounded-full border border-ember/40 px-4 py-2 text-sm text-ember transition hover:bg-ember/10"
              >
                Törlés
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {confirmPurge && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6"
          onClick={() => !purging && setConfirmPurge(null)}
        >
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="w-full max-w-sm rounded-2xl border border-ink-line bg-ink-card p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-sm leading-relaxed text-bone">
              Törlöd a(z) &ldquo;{confirmPurge.title}&rdquo; Portál összes fájlját (videók és képek) az R2 tárhelyből? A
              projekt megmarad, a kapcsolatfelvételi oldal továbbra is működik. Ez a művelet nem vonható vissza.
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <Button variant="ghost" size="sm" onClick={() => setConfirmPurge(null)} disabled={purging}>
                Mégse
              </Button>
              <button
                onClick={doPurge}
                disabled={purging}
                className="flex items-center gap-2 rounded-full border border-ember/40 px-4 py-2 text-sm text-ember transition hover:bg-ember/10 disabled:opacity-60"
              >
                <Trash2 className="h-4 w-4" />
                {purging ? "Törlés…" : "Fájlok törlése"}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </main>
  );
}
