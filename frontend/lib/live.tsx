"use client";

import { createContext, useCallback, useContext, useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { topicsForPath } from "@/lib/liveTopics";

/** Háttérfrissítés: az oldalt NEM kell újratölteni ahhoz, hogy meglássuk, ha
 * időközben új naptáresemény (projekt) érkezett, valaki hozzászólt, státuszt
 * írt át vagy értesítést kaptunk.
 *
 * Hogyan: néhány másodpercenként egyetlen olcsó kérés megy a backend
 * /realtime/changes végpontjára, ami csak egy ujjlenyomatot ad vissza témánként
 * (hány sor van, mikor módosult utoljára) - adatot nem. Ha az ujjlenyomat
 * változott, akkor - és csak akkor - kérjük újra a tényleges adatot.
 *
 * A tényleges frissítés a Next.js router.refresh(): a szerver-komponensek újra
 * lefutnak és a React összefésüli az eredményt a meglévő fával, tehát nem
 * "villan" az oldal, a görgetési pozíció megmarad, és a kliens-oldali állapot
 * (nyitott legördülők, félig kitöltött mezők) sem vész el.
 *
 * Amelyik komponens saját state-ben tartja a listáját (pl. a hozzászólások), az
 * a useLiveTopic() visszahívásában maga tölti újra magát - annak a router
 * frissítése önmagában nem elég. */

type Listener = () => void;

type Registration = {
  /** Hány komponens kéri ezt a témát - az utolsó leiratkozásnál esik ki. */
  refCount: number;
  listeners: Set<Listener>;
};

type LiveContextValue = {
  subscribe: (topic: string, onChange?: Listener) => () => void;
};

const LiveContext = createContext<LiveContextValue | null>(null);

const POLL_INTERVAL_MS = 6000;
const CHANGES_PATH = "/api/v1/realtime/changes";

export function LiveProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const registry = useRef(new Map<string, Registration>());
  const versions = useRef(new Map<string, string>());
  const inFlight = useRef(false);

  const subscribe = useCallback((topic: string, onChange?: Listener) => {
    const existing = registry.current.get(topic);
    const entry = existing ?? { refCount: 0, listeners: new Set<Listener>() };
    entry.refCount += 1;
    if (onChange) entry.listeners.add(onChange);
    registry.current.set(topic, entry);

    return () => {
      const current = registry.current.get(topic);
      if (!current) return;
      current.refCount -= 1;
      if (onChange) current.listeners.delete(onChange);
      if (current.refCount <= 0) {
        registry.current.delete(topic);
        // Az ujjlenyomatot is eldobjuk: ha a téma később visszakerül (pl.
        // visszalépünk az oldalra), a szerver-komponens úgyis friss adattal
        // rendereli - a régi ujjlenyomat csak egy fölösleges frissítést
        // váltana ki.
        versions.current.delete(topic);
      }
    };
  }, []);

  const poll = useCallback(async () => {
    if (inFlight.current || typeof document === "undefined" || document.hidden) return;
    const topics = [...registry.current.keys()];
    if (topics.length === 0) return;

    inFlight.current = true;
    try {
      const res = await authFetch(`${CHANGES_PATH}?topics=${encodeURIComponent(topics.join(","))}`);
      if (!res.ok) return;
      const data: Record<string, string> = await res.json();

      const changed: string[] = [];
      for (const [topic, version] of Object.entries(data)) {
        const previous = versions.current.get(topic);
        versions.current.set(topic, version);
        // Az első körben csak alapállapotot veszünk fel - a most betöltött
        // oldal adata definíció szerint friss, nem kell újratölteni.
        if (previous !== undefined && previous !== version) changed.push(topic);
      }
      if (changed.length === 0) return;

      for (const topic of changed) {
        for (const listener of registry.current.get(topic)?.listeners ?? []) listener();
      }
      router.refresh();
    } catch {
      // Hálózati hiba: a következő kör újrapróbálja, a felhasználót nem
      // zavarjuk vele (az oldal a régi adattal továbbra is használható).
    } finally {
      inFlight.current = false;
    }
  }, [router]);

  // Az útvonalhoz tartozó témák - így a legtöbb oldalnak semmit nem kell tennie
  // azért, hogy frissüljön (lásd lib/liveTopics.ts).
  useEffect(() => {
    const unsubscribers = topicsForPath(pathname).map((topic) => subscribe(topic));
    // Azonnal kérünk egy ujjlenyomatot, nem várunk az első körre: a kiindulási
    // állapotot ahhoz a pillanathoz kell rögzíteni, amikor az oldal adata
    // megjelent. Ha csak másodpercekkel később vennénk fel, az addig történt
    // változás beleolvadna az alapállapotba, és sosem frissülne az oldal.
    void poll();
    return () => unsubscribers.forEach((off) => off());
  }, [pathname, subscribe, poll]);

  useEffect(() => {
    const timer = window.setInterval(poll, POLL_INTERVAL_MS);
    // Amíg a fül háttérben van, nem kérdezgetünk (a poll magától kilép), de
    // amint visszatérünk rá, azonnal nézzük meg, mi történt közben.
    const onVisible = () => {
      if (!document.hidden) void poll();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [poll]);

  return <LiveContext.Provider value={{ subscribe }}>{children}</LiveContext.Provider>;
}

/** Egy komponens saját témát is figyelhet - jellemzően szűkítve egy rekordra
 * ("comments:12"). A visszahívás akkor fut, amikor a téma változott; ha a
 * komponens a saját state-jét tartja, ott töltse újra magát.
 *
 * A visszahívást ref-ben tartjuk, hogy egy sorközi függvény (`() => reload()`)
 * ne iratkozzon le és fel minden rendereléskor. */
export function useLiveTopic(topic: string | null, onChange?: Listener) {
  const live = useContext(LiveContext);
  const callback = useRef(onChange);

  useEffect(() => {
    callback.current = onChange;
  });

  useEffect(() => {
    if (!live || !topic) return;
    return live.subscribe(topic, () => callback.current?.());
  }, [live, topic]);
}
