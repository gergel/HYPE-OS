"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/authFetch";
import type { ProjectCode } from "@/lib/api";

type ProjectSummary = {
  id: number;
  nev: string;
  project_code_id: number;
  forgatas_datuma: string | null;
  forgatas_datuma_vege: string | null;
  helyszin: string | null;
  allapot: string | null;
  description: string | null;
};

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

/** Egy projekt gyors áttekintése felugró ablakban, teljes oldalra
 * navigálás helyett - a listás nézetből (táblázat vagy naptár) nyílik meg,
 * lásd ProjektekContent.tsx. Csak a legfontosabb mezőket mutatja (a teljes,
 * ~140 mezős, admin-szerkeszthető fülekkel ellátott részletnézet nem
 * ültethető át egy az egyben egy kliens-oldali popupba - lásd a
 * /projektek/[id]/page.tsx-et, ami szerver-oldali komponens, notFound()-ot
 * használ, és tucatnyi párhuzamos adatlekérést végez), ezért "Teljes nézet
 * megnyitása" linkkel mutat tovább mindenre, ami itt nincs. */
export function ProjectDetailModal({
  projectId,
  projectCodes,
  onClose,
}: {
  projectId: number | null;
  projectCodes: ProjectCode[];
  onClose: () => void;
}) {
  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (projectId === null) {
      setProject(null);
      return;
    }
    setLoading(true);
    setProject(null);
    authFetch(`/api/v1/projects/${projectId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setProject(data))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (projectId === null) return null;

  const projectCode = project ? projectCodes.find((pc) => pc.id === project.project_code_id) : undefined;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 px-6" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {loading || !project ? (
          <p className="text-[13px] text-text-secondary">Betöltés…</p>
        ) : (
          <>
            <h3 className="mb-1 text-[16px] font-medium text-text-primary">{project.nev}</h3>
            <p className="mb-4 text-[12px] text-text-muted">{projectCode?.projektkod ?? "–"}</p>
            <div className="grid grid-cols-2 gap-3 text-[13px]">
              <div>
                <p className="text-[11px] text-text-muted">Állapot</p>
                <p className="text-text-primary">{project.allapot ?? "–"}</p>
              </div>
              <div>
                <p className="text-[11px] text-text-muted">Forgatás dátuma</p>
                <p className="text-text-primary">
                  {formatDate(project.forgatas_datuma)}
                  {project.forgatas_datuma_vege && project.forgatas_datuma_vege !== project.forgatas_datuma
                    ? ` – ${formatDate(project.forgatas_datuma_vege)}`
                    : ""}
                </p>
              </div>
              <div className="col-span-2">
                <p className="text-[11px] text-text-muted">Helyszín</p>
                <p className="text-text-primary">{project.helyszin ?? "–"}</p>
              </div>
            </div>
            {project.description && (
              <div className="mt-3">
                <p className="text-[11px] text-text-muted">Leírás</p>
                <p className="whitespace-pre-wrap text-[13px] text-text-primary">{project.description}</p>
              </div>
            )}
            <div className="mt-5 flex justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={onClose}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
              >
                Bezárás
              </button>
              <a
                href={`/projektek/${project.id}`}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90"
              >
                Teljes nézet megnyitása →
              </a>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
