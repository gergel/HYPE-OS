"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, Globe } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { createPortalFromDeliverable } from "@/lib/portalAdminApi";
import { portalUrl } from "@/lib/portalUrl";

/** Az Utómunka részletnézetén megjelenő "Portál létrehozása" gomb - egy Média
 * Portált hoz létre közvetlenül ehhez a Deliverable-hez kötve (nem a
 * mögöttes Projekthez, mert egy Projektnek több Deliverable-je is lehet), és
 * a Portál TELJES, kiküldhető publikus linkjét (megosztó token-nel, mint a
 * Portál admin "Megosztó link" gombja) automatikusan beírja a "Kész anyag
 * URL" mezőbe. Az abszolút URL-t szándékosan itt, a böngészőben rakjuk
 * össze (lib/portalUrl.ts), nem a backend teszi ezt - a backend nem tudhatja
 * megbízhatóan a publikus domain-t minden környezetben, és enélkül csak a
 * relatív "/p/{slug}..." útvonal kerülne a mezőbe, amit nem lehet közvetlenül
 * kiküldeni a megrendelőnek. A link a PORTÁL domainjére mutat, nem az admin
 * felületére, ahol ez a gomb megnyomódik.
 * A Portál Admin listában (/media-portal) is megjelenik, mert ugyanabba a
 * `portals` táblába kerül, mint a projekt-alapú vagy kézi Portálok. */
export function CreatePortalButton({
  deliverableId,
  existingPortalId,
  keszAnyagUrl,
}: {
  deliverableId: number;
  existingPortalId: number | null;
  keszAnyagUrl: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (existingPortalId) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <a
          href={`/media-portal/${existingPortalId}`}
          className="flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
        >
          <Globe className="h-3.5 w-3.5" />
          Portál megnyitása
        </a>
        {keszAnyagUrl && (
          <a
            href={keszAnyagUrl}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-[12px] text-text-accent hover:underline"
          >
            {keszAnyagUrl}
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
    );
  }

  async function onCreate() {
    setBusy(true);
    setError(null);
    try {
      const portal = await createPortalFromDeliverable(deliverableId);
      const fullUrl = portalUrl(portal.slug, portal.share_token);
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}`, {
        method: "PATCH",
        body: JSON.stringify({ kesz_anyag_url: fullUrl }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setError(`A portál létrejött, de a "Kész anyag URL" mentése sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <p className="mb-2 text-[13px] text-text-secondary">
        Hozz létre egy Média Portált ehhez az anyaghoz - a publikus linkje automatikusan bekerül a "Kész anyag URL" mezőbe.
      </p>
      <button
        type="button"
        onClick={onCreate}
        disabled={busy}
        className="btn btn-primary"
      >
        <Globe className="h-4 w-4" />
        {busy ? "Létrehozás…" : "Portál létrehozása"}
      </button>
      {error && <p className="mt-2 text-[12px] text-text-danger">Sikertelen: {error}</p>}
    </div>
  );
}
