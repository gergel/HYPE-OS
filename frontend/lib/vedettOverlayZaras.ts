import type { MouseEvent } from "react";

/** Overlay-kattintásra záródó felugró ablakok VÉDETT zárása (a felhasználó
 * hibajelzése): szöveg kijelölése vagy húzás közben az egér könnyen az
 * overlay (a szürke háttér) fölött ér földet - a böngésző ilyenkor a
 * kattintás-eseményt az overlay-re futtatja, az ablak bezárult, és minden
 * beírt adat elveszett (pl. az új alvállalkozó űrlapja).
 *
 * A szabály: csak az a kattintás zár, amelyiknél a LENYOMÁS és a FELENGEDÉS
 * is magán az overlay-en történt. Ami az ablakon belül indult, az sosem zár -
 * akárhol is ér véget.
 *
 * Használat: `<div {...vedettOverlayZaras(onClose)} className="fixed inset-0 …">`
 * - a meglévő `onClick={onClose}` helyére. Renderenként új példány készül; ha
 * a lenyomás és a kattintás közt újrarenderelés történne, a jelző elveszik és
 * az ablak NEM záródik be - ez a biztonságos irány (legfeljebb még egy
 * kattintás kell a záráshoz), adat sosem vész el tőle. */
export function vedettOverlayZaras(onClose?: () => void) {
  let lenyomasAzOverlayen = false;
  return {
    onMouseDown: (e: MouseEvent) => {
      lenyomasAzOverlayen = e.target === e.currentTarget;
    },
    onClick: (e: MouseEvent) => {
      if (e.target === e.currentTarget && lenyomasAzOverlayen) onClose?.();
      lenyomasAzOverlayen = false;
    },
  };
}
