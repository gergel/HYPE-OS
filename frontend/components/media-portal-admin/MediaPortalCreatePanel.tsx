"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { authFetch } from "@/lib/authFetch";
import type { Project } from "@/lib/api";

/** Egy Portal mindig egy MEGLÉVŐ HYPE OS Project-hez kötött (1:1) - nincs
 * szabadon kitöltött cím/ügyfélnév, csak ki kell választani, melyik
 * projekthez tartozzon az új Portál. Csak azok a projektek jelennek meg,
 * amelyeknek még nincs Portáljuk (lásd page.tsx availableProjects szűrése). */
export function MediaPortalCreatePanel({ projects }: { projects: Project[] }) {
  const router = useRouter();
  const [projectId, setProjectId] = useState<number | "">("");
  const [busy, setBusy] = useState(false);

  async function create() {
    if (!projectId) return;
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/portal-admin", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      const created: { id: number } = await res.json();
      router.push(`/media-portal/${created.id}`);
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  if (projects.length === 0) {
    return <p className="text-[13px] text-text-muted">Minden projektnek már van Portálja.</p>;
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        value={projectId}
        onChange={(e) => setProjectId(e.target.value ? Number(e.target.value) : "")}
        className="rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-1.5 text-[13px] text-text-primary"
      >
        <option value="">Válassz projektet…</option>
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.nev}
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={busy || !projectId}
        onClick={create}
        className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        {busy ? "Létrehozás…" : "+ Új Portál"}
      </button>
    </div>
  );
}
