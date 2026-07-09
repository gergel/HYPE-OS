"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

const COUNT_KEY = "hype_nav_count";
const LAST_PATH_KEY = "hype_nav_last_path";

/** Nyomon követi, hány KÜLÖNBÖZŐ útvonalat látogatott meg a felhasználó ebben
 * a tab-ban (sessionStorage, tehát új tab-nál/ablaknál nullázódik, oldal-
 * frissítésnél megmarad) - ez adja a BackLink döntését, hogy a "← Vissza"
 * kattintás biztonságosan használhatja-e a valódi böngésző-history-t
 * (router.back()), vagy - mert a felhasználó közvetlen URL-lel/könyvjelzővel
 * nyitotta meg az oldalt, tehát nincs app-on belüli előzmény - inkább a
 * megadott alapértelmezett href-re kell navigálnia. Csak a pathname-eket
 * nézi (nem a query paramokat), hogy pl. egy lista szűrésének módosítása ne
 * számítson új "lépésnek". Ugyanazon útvonal újratöltése (frissítés) sem
 * növeli a számlálót, hogy ne higgyük tévesen, hogy van "vissza" cél. */
export function NavigationTracker() {
  const pathname = usePathname();

  useEffect(() => {
    const lastPath = sessionStorage.getItem(LAST_PATH_KEY);
    if (lastPath !== pathname) {
      const count = Number(sessionStorage.getItem(COUNT_KEY) || "0");
      sessionStorage.setItem(COUNT_KEY, String(count + 1));
      sessionStorage.setItem(LAST_PATH_KEY, pathname);
    }
  }, [pathname]);

  return null;
}
