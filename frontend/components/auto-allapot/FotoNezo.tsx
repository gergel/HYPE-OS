"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";

export type NezettFoto = { id: number; url: string; cimke: string; alcim: string };

/** Az állapotfotó FELUGRÓ ablakban (a felhasználó kérése: ne új oldalon
 * nyíljon). A kör képei között lapozni lehet: nyilakkal, a billentyűzet
 * nyilaival vagy húzással; Esc, az X vagy a háttérre kattintás bezárja. */
export function FotoNezo({
  fotok,
  index,
  onLapoz,
  onBezar,
}: {
  fotok: NezettFoto[];
  index: number;
  onLapoz: (index: number) => void;
  onBezar: () => void;
}) {
  const foto = fotok[index];
  const elozo = index > 0 ? index - 1 : null;
  const kovetkezo = index < fotok.length - 1 ? index + 1 : null;
  const [betoltott, setBetoltott] = useState<string | null>(null);
  const erintes = useRef<number | null>(null);
  const kezelok = useRef({ onLapoz, onBezar, elozo, kovetkezo });

  useEffect(() => {
    kezelok.current = { onLapoz, onBezar, elozo, kovetkezo };
  });

  useEffect(() => {
    function billentyu(e: KeyboardEvent) {
      const k = kezelok.current;
      if (e.key === "Escape") k.onBezar();
      else if (e.key === "ArrowLeft" && k.elozo !== null) k.onLapoz(k.elozo);
      else if (e.key === "ArrowRight" && k.kovetkezo !== null) k.onLapoz(k.kovetkezo);
    }
    window.addEventListener("keydown", billentyu);
    // A háttér ne görögjön, amíg nyitva van.
    const regi = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", billentyu);
      document.body.style.overflow = regi;
    };
  }, []);

  if (!foto) return null;

  const gomb =
    "absolute top-1/2 z-10 flex h-11 w-11 -translate-y-1/2 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={foto.cimke}
      className="fixed inset-0 z-[100] flex flex-col bg-black/90 backdrop-blur-sm"
      onClick={onBezar}
      onTouchStart={(e) => {
        erintes.current = e.touches[0].clientX;
      }}
      onTouchEnd={(e) => {
        if (erintes.current === null) return;
        const dx = e.changedTouches[0].clientX - erintes.current;
        erintes.current = null;
        if (dx > 50 && elozo !== null) onLapoz(elozo);
        else if (dx < -50 && kovetkezo !== null) onLapoz(kovetkezo);
      }}
    >
      <div className="flex shrink-0 items-start justify-between gap-3 px-4 py-3 text-white sm:px-6">
        <div className="min-w-0">
          <p className="text-[15px] font-semibold">{foto.cimke}</p>
          <p className="truncate text-[12.5px] text-white/70">
            {foto.alcim}
            {fotok.length > 1 && ` · ${index + 1} / ${fotok.length}`}
          </p>
        </div>
        <button
          type="button"
          aria-label="Bezárás"
          onClick={onBezar}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/10 hover:bg-white/20"
        >
          <X size={18} />
        </button>
      </div>

      <div className="relative flex min-h-0 flex-1 items-center justify-center px-4 pb-4 sm:px-16 sm:pb-8">
        {betoltott !== foto.url && <Loader2 className="absolute h-7 w-7 animate-spin text-white/70" />}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={foto.id}
          src={foto.url}
          alt={foto.cimke}
          onLoad={() => setBetoltott(foto.url)}
          onClick={(e) => e.stopPropagation()}
          className={`max-h-full max-w-full rounded-[var(--radius)] object-contain transition-opacity ${
            betoltott === foto.url ? "opacity-100" : "opacity-0"
          }`}
        />
        {elozo !== null && (
          <button
            type="button"
            aria-label="Előző kép"
            onClick={(e) => {
              e.stopPropagation();
              onLapoz(elozo);
            }}
            className={`${gomb} left-2 sm:left-4`}
          >
            <ChevronLeft size={22} />
          </button>
        )}
        {kovetkezo !== null && (
          <button
            type="button"
            aria-label="Következő kép"
            onClick={(e) => {
              e.stopPropagation();
              onLapoz(kovetkezo);
            }}
            className={`${gomb} right-2 sm:right-4`}
          >
            <ChevronRight size={22} />
          </button>
        )}
      </div>
    </div>
  );
}
