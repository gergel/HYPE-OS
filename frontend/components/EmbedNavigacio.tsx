"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

/** A felugró ablakba (iframe-be) ágyazott nézetek NAVIGÁCIÓ-KEZELŐJE.
 *
 * Két munkája van (a felhasználó hibajelzése alapján: az Utókövetés
 * ablakából egy személyre vagy szerződésre kattintva a TELJES alkalmazás -
 * oldalsávval, fejléccel - nyílt meg az ablakon belül):
 *
 * 1. A beágyazott nézeten belüli linkek NE a teljes alkalmazást töltsék be:
 *    aminek van keret nélküli (/embed/...) párja, az azon nyílik meg az
 *    ablakban; aminek nincs, az ÚJ BÖNGÉSZŐLAPON - alkalmazás az
 *    alkalmazásban így nem fordulhat elő.
 * 2. Minden útvonal-váltásról értesíti a szülő ablakot (postMessage), hogy a
 *    felugró ablak címe és "Megnyitás új oldalon" gombja mindig az ÉPPEN
 *    LÁTOTT tartalmat kövesse, ne ragadjon az elsőn. */

//: Amely útvonal-mintáknak VAN keret nélküli (/embed) párja - lásd app/embed/*.
const EMBED_MINTAK = [
  /^\/csapat\/\d+/,
  /^\/feladatok\/\d+/,
  /^\/felszereles\/\d+/,
  /^\/kampanyok\/\d+/,
  /^\/media-portal\/\d+/,
  /^\/penzugyek\/bevetel\/\d+/,
  /^\/penzugyek\/kiadas\/\d+/,
  /^\/projektek\/project-kodok\/\d+/,
  /^\/projektek\/\d+/,
  /^\/rekord\/[^/]+\/\d+/,
  /^\/szerzodesek\/\d+/,
  /^\/ugyfelek\/\d+/,
  /^\/utokovetes\/projektkodok\/\d+/,
  /^\/utokovetes\/\d+/,
  /^\/utomunka\/\d+/,
];

function vanEmbedParja(utvonal: string): boolean {
  return EMBED_MINTAK.some((m) => m.test(utvonal));
}

export function EmbedNavigacio() {
  const router = useRouter();
  const pathname = usePathname();

  // 2) A szülő ablak értesítése az aktuális tartalomról. A cím a lap fő
  // címsorából (h1) jön - kis késleltetéssel, hogy az új nézet ki is
  // renderelődjön.
  useEffect(() => {
    if (window.parent === window) return;
    const idozito = setTimeout(() => {
      // Csak a lap VALÓDI címsora megy át - a document.title alkalmazás-név
      // ("HYPE OS") címnek semmitmondó lenne a felugró ablak fejlécében.
      const cim = document.querySelector("h1")?.textContent?.trim() || "";
      window.parent.postMessage(
        { tipus: "embed-utvonal", utvonal: pathname.replace(/^\/embed/, ""), cim },
        window.location.origin,
      );
    }, 150);
    return () => clearTimeout(idozito);
  }, [pathname]);

  // 1) Link-elfogás: az iframe-en belüli belső linkek keret nélküli párra
  // váltanak, a többi új lapon nyílik.
  useEffect(() => {
    if (window.parent === window) return;

    function kattintas(e: MouseEvent) {
      // Módosítós kattintás (Ctrl/Cmd/középső gomb): hagyjuk a böngészőre.
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const cel = (e.target as HTMLElement | null)?.closest?.("a");
      if (!cel) return;
      const href = cel.getAttribute("href");
      if (!href || !href.startsWith("/") || href.startsWith("//")) return;
      if (href.startsWith("/embed/")) return; // már keret nélküli cél
      if (cel.target && cel.target !== "_self") return; // pl. target="_blank" fájl-linkek
      if (cel.hasAttribute("download")) return;
      e.preventDefault();
      const utvonal = href.split("?")[0].split("#")[0];
      if (vanEmbedParja(utvonal)) {
        router.push(`/embed${href}`);
      } else {
        // Nincs keret nélküli párja (pl. lista-oldal): új böngészőlapon a
        // teljes oldal - az ablakban nem ismétlődik meg az alkalmazás.
        window.open(href, "_blank", "noopener");
      }
    }

    document.addEventListener("click", kattintas, true);
    return () => document.removeEventListener("click", kattintas, true);
  }, [router]);

  return null;
}
