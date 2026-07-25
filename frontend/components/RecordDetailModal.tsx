"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Bármelyik rekord TELJES részletnézete felugró ablakban, teljes oldalra
 * navigálás helyett - a kapcsolódó rekordok tábláiból nyílik (lásd
 * RelatedTable), így pl. egy Külsősnél a hozzá tartozó szerződés egy
 * kattintással megnézhető anélkül, hogy elnavigálnánk a személy adatlapjáról.
 *
 * A tartalmat iframe-ben, az /embed/* útvonalról töltjük be, nem kliens
 * oldalon újraépítve: a részletnézetek szerver komponensek, sok párhuzamos,
 * sütire támaszkodó lekéréssel és szerver-oldalon összeállított widgetekkel.
 * Kliensbe portolva mindet újra kellene implementálni, és a két nézet
 * elcsúszna egymástól - így viszont szó szerint UGYANAZ a nézet jelenik meg,
 * minden művelettel együtt, egyetlen forrásból.
 *
 * A `href` a rendes alkalmazás-útvonal (pl. "/csapat/12"); az /embed előtag
 * elé illesztésével kapjuk a keret nélküli változatot (lásd app/embed). */
export function RecordDetailModal({ href, onClose }: { href: string | null; onClose: () => void }) {
  const router = useRouter();

  // Escape-re záródjon, és amíg nyitva van, a háttér ne görgethessen.
  useEffect(() => {
    if (!href) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [href, onClose]);

  if (!href) return null;

  /** Bezáráskor frissítjük a mögöttes oldalt: a felugró ablakban végzett
   * szerkesztés egyébként csak az iframe-en belül látszódna. */
  function close() {
    router.refresh();
    onClose();
  }

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 p-4" onClick={close}>
      <div
        role="dialog"
        aria-modal="true"
        className="flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-2.5">
          <span className="text-[13px] text-text-secondary">Részletek</span>
          <div className="flex items-center gap-2">
            <a
              href={href}
              className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[12px] text-text-secondary transition-colors hover:bg-bg-accent hover:text-text-accent hover:shadow-[0_0_0_1px_var(--accent-solid)]"
            >
              Megnyitás új oldalon →
            </a>
            <button
              type="button"
              onClick={close}
              className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[12px] text-text-secondary transition-colors hover:bg-bg-accent hover:text-text-accent hover:shadow-[0_0_0_1px_var(--accent-solid)]"
            >
              Bezárás
            </button>
          </div>
        </div>
        <iframe
          key={href}
          src={`/embed${href}`}
          title="Rekord részletei"
          className="min-h-0 flex-1 border-0 bg-background"
        />
      </div>
    </div>
  );
}
