"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, Globe } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { createPortalFromDeliverable, getPortalNevJavaslat } from "@/lib/portalAdminApi";
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
  const [ablakNyitva, setAblakNyitva] = useState(false);
  const [datum, setDatum] = useState("");
  //: A Portál KIFELÉ mutatott neve - az elnevezési útmutató szerinti
  //: javaslattal töltődik elő (lásd backend services/portal_nevjavaslat.py),
  //: és itt szabadon átírható; a Portálon utólag is szerkeszthető.
  const [nev, setNev] = useState("");
  const [nevInfo, setNevInfo] = useState<string | null>(null);
  const [javaslatTolt, setJavaslatTolt] = useState(false);

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
        title: nev.trim() || undefined,
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
      setAblakNyitva(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function onCreateClick() {
    // A létrehozás MINDIG a névjavaslatos ablakon át megy (a felhasználó
    // kérése): a rendszer az elnevezési útmutató szerinti pontos nevet
    // ajánl, ami itt átírható - és kötött forgatás nélkül a dátumot is itt
    // kérjük be (a backend enélkül el sem fogadja a létrehozást).
    setError(null);
    setNevInfo(null);
    setAblakNyitva(true);
    setJavaslatTolt(true);
    getPortalNevJavaslat(deliverableId)
      .then((j) => {
        setNev((elozo) => elozo || j.javaslat);
        setNevInfo(
          j.forras === "ai"
            ? j.indoklas || "Javaslat az elnevezési útmutató alapján."
            : "Javaslat a meglévő nevek tisztításából - ellenőrizd az útmutató szerint.",
        );
      })
      .catch(() => setNevInfo("A javaslat nem készült el - írd be a nevet kézzel."))
      .finally(() => setJavaslatTolt(false));
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
      {error && !ablakNyitva && <p className="mt-2 text-[12px] text-text-danger">Sikertelen: {error}</p>}

      {ablakNyitva && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-[var(--radius)] border border-border bg-surface-1 p-5 shadow-xl">
            <h3 className="mb-1 text-[15px] font-semibold text-text-primary">Portál létrehozása</h3>
            <p className="mb-3 text-[13px] text-text-secondary">
              Ez a név jelenik meg az ügyfélnek. A javaslat az elnevezési útmutató szerint készül
              („Ügyfél – Projekt vagy esemény”, belsős kódok nélkül) - szabadon átírhatod, és a Portálon
              utólag is szerkeszthető.
            </p>
            <label className="mb-1 block text-[12px] text-text-muted">A Portál neve</label>
            <input
              type="text"
              value={javaslatTolt && !nev ? "" : nev}
              onChange={(e) => setNev(e.target.value)}
              placeholder={javaslatTolt ? "Javaslat készítése…" : "pl. Bols – Mixer akadémia – Fotó"}
              autoFocus
              className="mb-1 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2 text-[14px] text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-border-strong"
            />
            {nevInfo && <p className="mb-2 text-[11.5px] text-text-muted">{nevInfo}</p>}

            {!forgatasDatum && (
              <>
                <label className="mb-1 mt-2 block text-[12px] text-text-muted">
                  A forgatás dátuma (nincs forgatás kötve, ezért kötelező)
                </label>
                <input
                  type="text"
                  value={datum}
                  onChange={(e) => setDatum(e.target.value)}
                  placeholder="pl. 2026.08.15. vagy 2026.08.15-17."
                  className="mb-2 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2 text-[14px] text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-1 focus:ring-border-strong"
                />
              </>
            )}
            {error && <p className="mb-3 text-[12px] text-text-danger">Sikertelen: {error}</p>}
            <div className="mt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setAblakNyitva(false);
                  setDatum("");
                  setNev("");
                  setError(null);
                }}
                disabled={busy}
                className="btn btn-ghost"
              >
                Mégse
              </button>
              <button
                type="button"
                onClick={() => void letrehozas(forgatasDatum ? undefined : datum)}
                disabled={busy || !nev.trim() || (!forgatasDatum && !datum.trim())}
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
