"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, Globe } from "lucide-react";
import { createPortalFromDeliverable } from "@/lib/portalAdminApi";

/** Az Utómunka részletnézetén megjelenő "Portál létrehozása" gomb - egy Média
 * Portált hoz létre közvetlenül ehhez a Deliverable-hez kötve (nem a
 * mögöttes Projekthez, mert egy Projektnek több Deliverable-je is lehet), és
 * a Portál publikus linkjét automatikusan beírja a "Kész anyag URL" mezőbe
 * (lásd backend/app/api/routes/portal_admin.py create_portal_from_deliverable).
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
      await createPortalFromDeliverable(deliverableId);
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
        className="flex items-center gap-1.5 rounded-[var(--radius)] px-4 py-2 text-[13px] font-medium text-white disabled:opacity-50"
        style={{ background: "var(--accent-gradient)" }}
      >
        <Globe className="h-4 w-4" />
        {busy ? "Létrehozás…" : "Portál létrehozása"}
      </button>
      {error && <p className="mt-2 text-[12px] text-text-danger">Sikertelen: {error}</p>}
    </div>
  );
}
