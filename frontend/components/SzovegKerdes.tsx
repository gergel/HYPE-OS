"use client";

import { useCallback, useState, type ReactNode } from "react";
import { ModalReteg } from "@/components/ModalReteg";

type Nyitott = { kerdes: string; alap: string; valasz: (ertek: string | null) => void };

/** A böngésző `window.prompt`-jának oldalon belüli párja.
 *
 * Miért kell: a `window.prompt` sok helyen egyszerűen NEM jelenik meg -
 * alkalmazásból megnyitott (beépített) böngészőben, telefonos webview-ban,
 * vagy ha valaki a Chrome-ban egyszer bepipálta, hogy „ne engedje további
 * párbeszédablakok megnyitását”. Ilyenkor azonnal üreset ad vissza, és a gomb
 * csendben nem csinál semmit (a felhasználó jelezte: az árajánlatban nem
 * lehetett új szekciót készíteni).
 *
 * Használat: `const { kerdez, ablak } = useSzovegKerdes()`, az `ablak`-ot a
 * komponens kimenetébe kell tenni, és `await kerdez("Kérdés", "alapérték")`
 * ugyanazt adja, mint a prompt: a beírt szöveget, Mégse esetén `null`-t. */
export function useSzovegKerdes(): { kerdez: (kerdes: string, alap?: string) => Promise<string | null>; ablak: ReactNode } {
  const [nyitott, setNyitott] = useState<Nyitott | null>(null);
  const [ertek, setErtek] = useState("");

  const kerdez = useCallback(
    (kerdes: string, alap = "") =>
      new Promise<string | null>((resolve) => {
        setErtek(alap);
        setNyitott({ kerdes, alap, valasz: resolve });
      }),
    [],
  );

  function lezar(valasz: string | null) {
    nyitott?.valasz(valasz);
    setNyitott(null);
  }

  const ablak = nyitott ? (
    <ModalReteg onClose={() => lezar(null)}>
      <form
        className="mt-[12vh] w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-2 p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => {
          e.preventDefault();
          lezar(ertek);
        }}
      >
        <label className="block text-[13.5px] font-medium text-text-primary" htmlFor="szoveg-kerdes">
          {nyitott.kerdes}
        </label>
        <input
          id="szoveg-kerdes"
          autoFocus
          value={ertek}
          onChange={(e) => setErtek(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.preventDefault();
              lezar(null);
            }
          }}
          onFocus={(e) => e.target.select()}
          className="field mt-2 w-full"
        />
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={() => lezar(null)}>
            Mégse
          </button>
          <button type="submit" className="btn btn-primary">
            Rendben
          </button>
        </div>
      </form>
    </ModalReteg>
  ) : null;

  return { kerdez, ablak };
}
