"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { RecordDetailModal } from "@/components/RecordDetailModal";
import { felugroTerulet, vanEmbedParja } from "@/lib/felugro";

/** Megnyitás felugró ablakban - `true`, ha elvállalta (és akkor a hívó NE
 * navigáljon), `false`, ha nem (nem felugró területen vagyunk, vagy a célnak
 * nincs keret nélküli párja). */
type Nyitas = (href: string) => boolean;

const FelugroContext = createContext<Nyitas | null>(null);

/** A felugró-ablak nyitója - a sor-kattintásokhoz (lásd RowLink), amik nem
 * <a> elemen át navigálnak. Provider nélkül null: akkor marad a navigáció. */
export function useFelugroNyitas(): Nyitas | null {
  return useContext(FelugroContext);
}

/** MINDEN MEGNYITÁS FELUGRÓ ABLAKBAN a Pénzügyek csoportban és a
 * projektkódoknál (a felhasználó kérése) - lásd lib/felugro.FELUGRO_TERULETEK.
 *
 * Nem oldalanként, linkenként kell átírni: egy dokumentum-szintű kattintás-
 * figyelő elfogja a belső linkeket, és ha a célnak van keret nélküli (/embed)
 * párja, a RecordDetailModal-ban nyitja meg, navigáció helyett. A táblázat-
 * sorok (RowLink) a contexten át kérik ugyanezt. Aminek nincs /embed párja
 * (lista-oldalak, oldalsáv), az a megszokott módon navigál.
 *
 * Kihagyható egy link a `data-felugro-kihagy` attribútummal (pl. a felugró
 * ablak saját „Megnyitás új oldalon” gombja). A módosítós kattintás
 * (Ctrl/Cmd/középső gomb) a böngészőé marad - új lapon nyílik, ahogy eddig. */
export function FelugroAblak({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  // Az ablak azon az oldalon él, ahol megnyitották: oldalváltáskor (pl.
  // oldalsáv) magától eltűnik - nem kell effektben bezárni.
  const [nyitott, setNyitott] = useState<{ href: string; oldal: string } | null>(null);
  const href = nyitott && nyitott.oldal === pathname ? nyitott.href : null;

  const nyit = useCallback<Nyitas>((cel) => {
    if (!felugroTerulet(window.location.pathname)) return false;
    if (!cel.startsWith("/") || cel.startsWith("//") || cel.startsWith("/embed/")) return false;
    if (!vanEmbedParja(cel)) return false;
    // Ugyanarra az oldalra mutató link (pl. horgony) nem nyit ablakot.
    if (cel.split("?")[0].split("#")[0] === window.location.pathname) return false;
    setNyitott({ href: cel, oldal: window.location.pathname });
    return true;
  }, []);

  useEffect(() => {
    function kattintas(e: MouseEvent) {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const cel = (e.target as HTMLElement | null)?.closest?.("a");
      if (!cel || cel.closest("[data-felugro-kihagy]")) return;
      if (cel.target && cel.target !== "_self") return;
      if (cel.hasAttribute("download")) return;
      const celHref = cel.getAttribute("href");
      if (celHref && nyit(celHref)) e.preventDefault();
    }
    // Capture fázis: a Next <Link> saját kezelője előtt fut, és a
    // preventDefault után az már nem navigál.
    document.addEventListener("click", kattintas, true);
    return () => document.removeEventListener("click", kattintas, true);
  }, [nyit]);

  return (
    <FelugroContext.Provider value={nyit}>
      {children}
      <RecordDetailModal href={href} onClose={() => setNyitott(null)} />
    </FelugroContext.Provider>
  );
}
