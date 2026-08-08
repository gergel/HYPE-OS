"use client";

import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** Felugró ablak rétege: a tartalmat a `<body>` VÉGÉRE teszi ki, nem oda, ahol
 * a komponens áll.
 *
 * Miért kell ez, és miért nem elég a sima `position: fixed`: a fixed elem
 * pozíciója nem a képernyőhöz, hanem a legközelebbi olyan ősdobozhoz igazodik,
 * amin transform (vagy filter) van - a rendszer `fade-in` osztálya pedig épp
 * ilyen animációt használ. Egy ilyen dobozba ágyazva (pl. az autó lenyitott
 * lapján) az ablak nem a képernyő közepére, hanem a doboz közepére került, és
 * a teteje kilógott a képből. A portál ezt tünteti el: az ablak mindig a
 * dokumentum tetején él, akárhonnan is nyitották.
 *
 * A réteg maga GÖRGETHETŐ, és felülre igazít: egy hosszú űrlap alacsony
 * képernyőn se veszítse el a saját fejlécét és az első mezőit. */
export function ModalReteg({ onClose, children }: { onClose?: () => void; children: ReactNode }) {
  // Szerveren nincs `document`, ezért csak beillesztés után portálozunk.
  const [mount, setMount] = useState(false);
  useEffect(() => setMount(true), []);
  if (!mount) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[120] flex items-start justify-center overflow-y-auto bg-black/60 px-6 py-10"
      onClick={onClose}
    >
      {children}
    </div>,
    document.body,
  );
}
