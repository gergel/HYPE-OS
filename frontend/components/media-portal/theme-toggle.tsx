"use client";
import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";

/**
 * Téma-kapcsoló a portálhoz.
 * - Alapból VILÁGOS (ha nincs korábbi választás).
 * - A választást localStorage jegyzi meg ("hype_portal_theme").
 * - NEM nyúl közvetlenül a DOM-hoz (nincs classList manipuláció a <html>-en),
 *   mert az ütközik a React renderelésével (removeChild hiba). Helyette a
 *   szülő komponensnek szól az onChange callbacken keresztül, és a szülő
 *   egy React-vezérelt wrapper osztállyal adja a dark témát.
 */
export function ThemeToggle({ dark, onChange }: { dark: boolean; onChange: (dark: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!dark)}
      aria-label={dark ? "Váltás világos témára" : "Váltás sötét témára"}
      title={dark ? "Világos téma" : "Sötét téma"}
      className="flex h-10 w-10 items-center justify-center rounded-full border border-ink-line bg-ink-card text-bone transition hover:border-ember/60"
    >
      {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
    </button>
  );
}

/**
 * Hook a téma-állapot kezeléséhez (localStorage-ből olvas, oda ír).
 */
export function usePortalTheme() {
  const [dark, setDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("hype_portal_theme");
    setDark(saved === "dark");
    setMounted(true);
  }, []);

  function setTheme(next: boolean) {
    setDark(next);
    localStorage.setItem("hype_portal_theme", next ? "dark" : "light");
  }

  return { dark, setTheme, mounted };
}
