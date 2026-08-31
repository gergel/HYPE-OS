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
 * a Portál LETISZTULT publikus linkjét (a sima /p/{slug} címet, share token
 * nélkül - ugyanazt, amit a Portál admin "Megosztó link" gombja ad)
 * automatikusan beírja a "Kész anyag URL" mezőbe. Az abszolút URL-t
 * szándékosan itt, a böngészőben rakjuk össze (lib/portalUrl.ts), nem a
 * backend teszi ezt - a backend nem tudhatja megbízhatóan a publikus
 * domain-t minden környezetben, és enélkül csak a relatív "/p/{slug}"
 * útvonal kerülne a mezőbe, amit nem lehet közvetlenül kiküldeni a
 * megrendelőnek. A link a PORTÁL domainjére mutat, nem az admin felületére,
 * ahol ez a gomb megnyomódik.
 *
 * A Portálon megjelenő dátum a FORGATÁS dátuma: ha az utómunkához forgatás
 * van kötve, onnan megy magától (forgatasDatum prop); ha nincs, a gomb
 * felugró ablakban kéri be, és KÖTELEZŐ megadni (a felhasználó kérése).
 *
 * A Portál Admin listában (/media-portal) is megjelenik, mert ugyanabba a
 * `portals` táblába kerül, mint a projekt-alapú vagy kézi Portálok. */
export function CreatePortalButton({
  deliverableId,
  existingPortalId,
  keszAnyagUrl,
  forgatasDatum,
}: {
  deliverableId: number;
  existingPortalId: number | null;
  keszAnyagUrl: string | null;
  /** A kötött forgatás (Project) dátuma ISO formában ("2026-09-12"), vagy
   * null, ha az utómunkához nincs forgatás kötve. */
  forgatasDatum: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [datumKerdes, setDatumKerdes] = useState(false);
  const [datum, setDatum] = useState("");

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

  async function letrehozas(kezziDatum?: string) {
    setBusy(true);
    setError(null);
    try {
      // A kézzel beírt dátum SZABAD SZÖVEG (a felhasználó kérése): mehet bele
      // tartomány ("2026.08.15-17.") vagy bármilyen felirat, ugyanúgy, ahogy
      // a Portál admin dátum-mezőjébe - változtatás nélkül továbbítjuk.
      const portal = await createPortalFromDeliverable(deliverableId, {
        forgatasDatum: kezziDatum?.trim() || undefined,
      });
      const fullUrl = portalUrl(portal.slug);
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}`, {
        method: "PATCH",
        body: JSON.stringify({ kesz_anyag_url: fullUrl }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setError(`A portál létrejött, de a "Kész anyag URL" mentése sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      setDatumKerdes(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function onCreateClick() {
    // Kötött forgatás nélkül a dátumot KÖTELEZŐ bekérni - a backend enélkül
    // el sem fogadja a létrehozást.
    if (!forgatasDatum) {
      setError(null);
      setDatumKerdes(true);
      return;
    }
    void letrehozas();
  }

  return (
    <div>
      <p className="mb-2 text-[13px] text-text-secondary">
        Hozz létre egy Média Portált ehhez az anyaghoz - a publikus linkje automatikusan bekerül a &quot;Kész anyag URL&quot; mezőbe.
      </p>
      <button
        type="button"
        onClick={onCreateClick}
        disabled={busy}
        className="btn btn-primary"
      >
        <Globe className="h-4 w-4" />
        {busy ? "Létrehozás…" : "Portál létrehozása"}
      </button>
      {error && !datumKerdes && <p className="mt-2 text-[12px] text-text-danger">Sikertelen: {error}</p>}

      {datumKerdes && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-sm rounded-[var(--radius)] border border-border bg-surface-1 p-5 shadow-xl">
            <h3 className="mb-1 text-[15px] font-semibold text-text-primary">Mi volt a forgatás dátuma?</h3>
            <p className="mb-4 text-[13px] text-text-secondary">
              Ehhez az utómunkához nincs forgatás kötve, ezért a Portálon megjelenő forgatási dátumot itt kell
              megadni - enélkül nem jön létre a Portál.
            </p>
            <input
              type="text"
              value={datum}
              onChange={(e) => setDatum(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && datum.trim() && !busy) void letrehozas(datum);
              }}
              placeholder="pl. 2026.08.15. vagy 2026.08.15-17."
              autoFocus
              className="mb-4 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2 text-[14px] text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-border-strong"
            />
            {error && <p className="mb-3 text-[12px] text-text-danger">Sikertelen: {error}</p>}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setDatumKerdes(false);
                  setDatum("");
                  setError(null);
                }}
                disabled={busy}
                className="btn btn-ghost"
              >
                Mégse
              </button>
              <button
                type="button"
                onClick={() => void letrehozas(datum)}
                disabled={busy || !datum.trim()}
                className="btn btn-primary"
              >
                {busy ? "Létrehozás…" : "Portál létrehozása"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
