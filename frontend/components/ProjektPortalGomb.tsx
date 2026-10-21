"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Globe } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { createPortal } from "@/lib/portalAdminApi";
import { portalUrl } from "@/lib/portalUrl";

type PortalAdat = { id: number; slug: string; deliverable_id: number | null };

/** A PROJEKT (diszpó) oldal Média Portál vezérlője (a felhasználó kérése):
 *
 * - ha a munkának MÁR VAN Portálja - akár innen, akár az Utómunkán keresztül
 *   jött létre -, azt mutatja meg és nyitja, nem enged másodikat;
 * - ha nincs, innen is létrehozható - és a backend automatikusan beköti a
 *   projekt utómunkájához is, hogy a vágók ugyanazon dolgozzanak (lásd
 *   backend portal_admin.create_portal), a publikus link pedig bekerül az
 *   anyag "Kész anyag URL" mezőjébe (mint az Utómunka-oldali gombnál).
 */
export function ProjektPortalGomb({ projectId }: { projectId: number }) {
  const [portal, setPortal] = useState<PortalAdat | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  useEffect(() => {
    authFetch(`/api/v1/portal-admin/projekt/${projectId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((adat: PortalAdat | null) => setPortal(adat))
      .catch(() => setPortal(null));
  }, [projectId]);

  async function letrehozas() {
    setBusy(true);
    setHiba(null);
    try {
      const uj = await createPortal(projectId);
      // A publikus link az utómunka "Kész anyag URL" mezőjébe - ugyanaz a
      // minta, mint az Utómunka-oldali gombnál (CreatePortalButton): az
      // abszolút URL-t a böngésző rakja össze, a backend nem ismeri
      // megbízhatóan a publikus domaint.
      if (uj.deliverable_id) {
        await authFetch(`/api/v1/deliverables/${uj.deliverable_id}`, {
          method: "PATCH",
          body: JSON.stringify({ kesz_anyag_url: portalUrl(uj.slug) }),
        }).catch(() => null);
      }
      setPortal({ id: uj.id, slug: uj.slug, deliverable_id: uj.deliverable_id ?? null });
    } catch (err) {
      setHiba(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (portal === undefined) {
    return <p className="text-[13px] text-text-muted">Betöltés…</p>;
  }

  if (portal) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <a
          href={`/media-portal/${portal.id}`}
          className="flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
        >
          <Globe className="h-3.5 w-3.5" />
          Portál megnyitása
        </a>
        <a
          href={portalUrl(portal.slug)}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 text-[12px] text-text-accent hover:underline"
        >
          {portalUrl(portal.slug)}
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    );
  }

  return (
    <div>
      <p className="mb-2 text-[13px] text-text-secondary">
        Ehhez a munkához még nincs Média Portál. Innen létrehozva automatikusan az utómunkához is bekötődik, hogy a
        vágók ugyanazon dolgozzanak.
      </p>
      <button type="button" onClick={() => void letrehozas()} disabled={busy} className="btn btn-primary">
        <Globe className="h-4 w-4" />
        {busy ? "Létrehozás…" : "Portál létrehozása"}
      </button>
      {hiba && <p className="mt-2 text-[12px] text-text-danger">Sikertelen: {hiba}</p>}
    </div>
  );
}
