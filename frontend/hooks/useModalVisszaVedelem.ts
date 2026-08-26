"use client";

import { useEffect, useRef } from "react";

/** Amíg egy felugró ablak nyitva van, egy plusz réteget told a böngésző
 * előzményeibe - így egy VISSZA lépés (billentyű, egér "vissza" gombja, vagy
 * touchpaden az oldalra suhintás) először csak az ablakot csukja be, nem
 * navigál el a mögötte lévő oldalról.
 *
 * Enélkül a natív vissza-navigáció megkerüli a Reactot: nem az `onClose`-t
 * hívja meg, hanem egyből elviszi a böngészőt az előző oldalra - ami egy
 * megnyitott projektnél pont azt jelenti, hogy az egész nézetből kidob, nem
 * csak a felugró ablakot csukja be.
 *
 * A `pushState({}, "")` nem ad meg URL-t, tehát a címsor nem változik - ez
 * NEM navigáció, a Next.js router ezért nem is reagál rá semmivel.
 *
 * Ha az ablak MÁSKÉNT záródik (Escape, háttérre kattintás, Bezárás gomb),
 * akkor a takarításkor egy `history.back()`-kel kell letolni a mesterséges
 * réteget - de előbb le kell iratkozni a popstate eseményről, különben ez a
 * saját maga generálta vissza-lépés újra lefuttatná az `onClose`-t. */
export function useModalVisszaVedelem(nyitva: boolean, onClose: () => void): void {
  const visszaLepesTortent = useRef(false);

  useEffect(() => {
    if (!nyitva) return;

    window.history.pushState({ modalReteg: true }, "");
    visszaLepesTortent.current = false;

    function onPopState() {
      visszaLepesTortent.current = true;
      onClose();
    }

    window.addEventListener("popstate", onPopState);
    return () => {
      window.removeEventListener("popstate", onPopState);
      if (!visszaLepesTortent.current) {
        window.history.back();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nyitva]);
}
