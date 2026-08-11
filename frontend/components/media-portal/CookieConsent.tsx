"use client";
import { useEffect, useState } from "react";
import { pixelGrantConsent, pixelRejectConsent } from "@/lib/barionPixel";

const STORAGE_KEY = "hype_cookie_consent";

/** Süti-sáv a PUBLIKUS portálon.
 *
 * A Barion Full Pixel csak akkor küldhet marketing adatot, ha a néző ehhez
 * kifejezetten hozzájárult - ezt a döntést jelezzük a Pixelnek (grantConsent /
 * rejectConsent), és a böngészőben megjegyezzük, hogy ne kérdezzünk újra.
 *
 * Csak az ügyfeleknek szóló portál-oldalakon jelenik meg: a belső HYPE OS
 * felületen nincs követés, tehát nincs mihez hozzájárulni. */
export function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "granted") {
        // Korábban elfogadta — a Pixelnek újra jelezzük a hozzájárulást
        pixelGrantConsent();
      } else if (!stored) {
        // Még nem döntött — mutatjuk a sávot
        setVisible(true);
      }
    } catch {
      setVisible(true);
    }
  }, []);

  function accept() {
    try {
      localStorage.setItem(STORAGE_KEY, "granted");
    } catch {}
    pixelGrantConsent();
    setVisible(false);
  }

  function reject() {
    try {
      localStorage.setItem(STORAGE_KEY, "rejected");
    } catch {}
    pixelRejectConsent();
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-[120] p-4">
      <div className="mx-auto flex max-w-3xl flex-col gap-4 rounded-2xl border border-ink-line bg-ink-card p-5 shadow-2xl sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm leading-relaxed text-mist">
          Sütiket használunk a biztonságos fizetés és a szolgáltatás működése érdekében.
          A részletekért lásd az{" "}
          <a
            href="/adatvedelem"
            className="text-bone underline underline-offset-4 transition hover:text-ember"
          >
            Adatkezelési Tájékoztatót
          </a>
          .
        </p>
        <div className="flex shrink-0 gap-3">
          <button
            onClick={reject}
            className="rounded-full border border-ink-line px-5 py-2.5 text-sm text-mist transition hover:text-bone"
          >
            Elutasítás
          </button>
          <button
            onClick={accept}
            className="rounded-full bg-ember px-5 py-2.5 text-sm font-medium text-white transition hover:bg-ember/90"
          >
            Elfogadás
          </button>
        </div>
      </div>
    </div>
  );
}
