"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useModalVisszaVedelem } from "@/hooks/useModalVisszaVedelem";

/** Egy projekt TELJES részletnézete felugró ablakban, teljes oldalra navigálás
 * helyett - a listás/naptár nézetből nyílik (lásd ProjektekContent.tsx,
 * NaptarDiszpoContent.tsx).
 *
 * A tartalmat iframe-ben, a /embed/projektek/[id] útvonalról töltjük be, nem
 * kliens oldalon újraépítve: a részletnézet szerver komponens, ~14 párhuzamos,
 * sütire támaszkodó lekéréssel és egy csomó szerver-oldalon összeállított
 * widgettel (lásd ProjectDetailContent.tsx). Kliensbe portolva ezt mind újra
 * kellene implementálni, és a két nézet előbb-utóbb elcsúszna egymástól -
 * így viszont szó szerint UGYANAZ a nézet jelenik meg, minden művelettel
 * együtt, egyetlen forrásból. */
export function ProjectDetailModal({
  projectId,
  onClose,
  nezet,
}: {
  projectId: number | null;
  onClose: () => void;
  /** HONNAN nyílt meg. A Diszpó oldalról a diszpós munkájához kell a projekt
   * (gyártás, technika, stáb, a két küldés) - a papírozás és a költségek oda
   * csak zajt vinnének. A Projektek listából ugyanez a projekt TELJESEN
   * nyílik meg. Lásd ProjectDetailContent `csakDiszpoNezet`. */
  nezet?: "diszpo";
}) {
  const router = useRouter();

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

  /** Bezáráskor frissítjük a mögöttes listát: a felugró ablakban végzett
   * szerkesztés (állapot, dátum, törlés) egyébként csak az iframe-en belül
   * látszódna, a mögötte lévő táblázat/naptár a régi adatot mutatná. */
  function close() {
    router.refresh();
    onClose();
  }

  // Egy VISSZA lépés (touchpad suhintás is) csak ezt az ablakot csukja be,
  // nem navigál el a mögötte lévő oldalról.
  useModalVisszaVedelem(projectId !== null, close);

  if (projectId === null) return null;

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 p-4" onClick={close}>
      <div
        role="dialog"
        aria-modal="true"
        className="flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-2.5">
          <span className="text-[13px] text-text-secondary">Projekt részletei</span>
          <div className="flex items-center gap-2">
            <a
              href={`/projektek/${projectId}`}
              className="btn btn-ghost !text-[12px]"
            >
              Megnyitás új oldalon →
            </a>
            <button
              type="button"
              onClick={close}
              className="btn btn-ghost !text-[12px]"
            >
              Bezárás
            </button>
          </div>
        </div>
        <iframe
          key={projectId}
          src={`/embed/projektek/${projectId}${nezet ? `?nezet=${nezet}` : ""}`}
          title="Projekt részletei"
          className="min-h-0 flex-1 border-0 bg-background"
        />
      </div>
    </div>
  );
}
