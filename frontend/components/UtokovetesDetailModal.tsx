"use client";

import { useEffect, useRef, useState } from "react";
import { vedettOverlayZaras } from "@/lib/vedettOverlayZaras";
import { useRouter } from "next/navigation";
import { useModalVisszaVedelem } from "@/hooks/useModalVisszaVedelem";

/** Egy projekt utókövetés-részletnézete felugró ablakban, teljes oldalra
 * navigálás helyett - az Utókövetés listáiból nyílik (lásd UtokovetesLista,
 * UtokovetesTabla).
 *
 * Ugyanaz a minta, mint a ProjectDetailModal-nál, és ugyanazért: a tartalmat
 * iframe-ben, az /embed/utokovetes/[id] útvonalról töltjük be, nem kliens
 * oldalon újraépítve. A részletnézet szerver komponens, kilenc párhuzamos
 * lekéréssel és egy sor szerver-oldalon összeállított widgettel - kliensbe
 * portolva mindezt újra kellene írni, és a két nézet előbb-utóbb elcsúszna
 * egymástól. Így viszont szó szerint UGYANAZ a nézet jelenik meg, minden
 * művelettel (szerződés, TIG, törlés, állapotváltás) együtt.
 *
 * A lista mögötte marad: aki végigmegy tíz projekten, nem veszíti el a
 * szűrését és a görgetési helyét minden egyes megnyitásnál.
 *
 * NEGATÍV projectId = PROJEKTKÓD: az utókövetés egyetlen közös listája
 * (a felhasználó kérése) forgatásos projekteket ÉS forgatás nélküli,
 * projektkód-szintű papírozást is tartalmaz - utóbbiak azonosítója
 * -project_code_id-ként utazik (lásd app/(app)/utokovetes/page.tsx), és a
 * projektkód-részletnézet nyílik rájuk. */
export function UtokovetesDetailModal({
  projectId,
  onClose,
}: {
  projectId: number | null;
  onClose: () => void;
}) {
  const router = useRouter();
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  // Az ablakon BELÜLI navigáció követése: az /embed nézet minden útvonal-
  // váltásnál postMessage-et küld (lásd components/EmbedNavigacio.tsx) - a
  // cím és a "Megnyitás új oldalon" gomb így mindig az ÉPPEN LÁTOTT
  // tartalomra mutat, nem ragad az elsőn (a felhasználó hibajelzése).
  const [aktualis, setAktualis] = useState<{ utvonal: string; cim: string } | null>(null);

  useEffect(() => {
    function uzenet(e: MessageEvent) {
      if (e.origin !== window.location.origin) return;
      const adat = e.data as { tipus?: string; utvonal?: string; cim?: string };
      if (adat?.tipus === "embed-utvonal" && typeof adat.utvonal === "string") {
        setAktualis({ utvonal: adat.utvonal, cim: adat.cim || "" });
      }
    }
    window.addEventListener("message", uzenet);
    return () => window.removeEventListener("message", uzenet);
  }, []);

  // Új rekord megnyitásakor tiszta lappal indulunk - az előző projekt címe
  // és útvonala nem maradhat látható.
  useEffect(() => {
    setAktualis(null);
  }, [projectId]);

  // Escape-re záródjon, és amíg nyitva van, a háttér ne görgethessen.
  useEffect(() => {
    if (projectId === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [projectId, onClose]);

  /** Bezáráskor frissítjük a mögöttes listát: a felugró ablakban elvégzett
   * papírozás (szerződés kiküldése, TIG törlése) egyébként csak az iframe-en
   * belül látszódna, a mögötte lévő táblázat a régi állapotot mutatná. */
  function close() {
    router.refresh();
    onClose();
  }

  // Egy VISSZA lépés (touchpad suhintás is) csak ezt az ablakot csukja be,
  // nem navigál el a mögötte lévő oldalról.
  useModalVisszaVedelem(projectId !== null, close);

  if (projectId === null) return null;

  const utvonal = projectId < 0 ? `/utokovetes/projektkodok/${-projectId}` : `/utokovetes/${projectId}`;
  // A fejléc mindig az ÉPPEN LÁTOTT tartalomról beszél - az ablakon belüli
  // továbbnavigálás (személy, szerződés) után is.
  const lattottUtvonal = aktualis?.utvonal || utvonal;
  const elnavigalt = lattottUtvonal !== utvonal;
  const cim = aktualis?.cim ? `Utókövetés · ${aktualis.cim}` : "Utókövetés";

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 p-4" {...vedettOverlayZaras(close)}>
      <div
        role="dialog"
        aria-modal="true"
        className="flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-2.5">
          <span className="truncate text-[13px] text-text-secondary">{cim}</span>
          <div className="flex shrink-0 items-center gap-2">
            {elnavigalt && (
              <button
                type="button"
                onClick={() => iframeRef.current?.contentWindow?.history.back()}
                className="btn btn-ghost !text-[12px]"
              >
                ← Vissza
              </button>
            )}
            <a href={lattottUtvonal} target="_blank" rel="noopener noreferrer" className="btn btn-ghost !text-[12px]">
              Megnyitás új oldalon →
            </a>
            <button type="button" onClick={close} className="btn btn-ghost !text-[12px]">
              Bezárás
            </button>
          </div>
        </div>
        <iframe
          ref={iframeRef}
          key={projectId}
          src={`/embed${utvonal}`}
          title={cim}
          className="min-h-0 flex-1 border-0 bg-background"
        />
      </div>
    </div>
  );
}
