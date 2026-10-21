"use client";

import { useEffect } from "react";

/** A Krumpello arculatát a `<body>`-ra is felteszi, amíg ezen a felületen
 * vagyunk.
 *
 * Miért kell, ha a layout már egy `.krumpello-root` dobozba teszi a tartalmat?
 * Mert a felugró ablakok egy része a `<body>` VÉGÉRE portálozik (lásd
 * ModalReteg és a benne leírt indoklást), tehát kilép abból a dobozból - és
 * ott már a HYPE OS alaptokenjeit örökölné. Egy Krumpello-oldalról nyíló ablak
 * így titánszürkén jelenne meg a narancs helyett.
 *
 * A takarítás (a class levétele) azért fontos, mert a HYPE OS-be visszalépve
 * ugyanaz a `<body>` marad - class nélkül viszont ott sosem volt Krumpello. */
export function KrumpelloTemaTest() {
  useEffect(() => {
    document.body.classList.add("krumpello-root");
    return () => document.body.classList.remove("krumpello-root");
  }, []);
  return null;
}
