"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronRight, Loader2, RotateCcw, X } from "lucide-react";

/** BEÉPÍTETT KAMERA az állapotfotókhoz (a felhasználó kérése).
 *
 * A telefon saját kamerája a kép után "Retake / Use Photo" kérdést tesz fel,
 * amit a weboldal nem tud átírni. Ezért itt saját kamera fut (getUserMedia):
 * élő kép, exponálás, utána két gomb - "Újra" (újrafotózás) és
 * "Következő: <rész>" (ez az ELFOGADÁS: a kép rendben, mehet fel, és rögtön a
 * következő rész jön ugyanebben a nézetben). A kamera a részek között nyitva
 * marad, így nem kér újra engedélyt.
 *
 * Ha a kamera nem indítható (nincs engedély, nem támogatott), `onHiba`-val
 * szól - a hívó ilyenkor a telefon saját kamerájára vált vissza. */
export function KameraNezet({
  cim,
  lepes,
  utmutatoSzoveg,
  kovetkezoCimke,
  onElfogad,
  onBezar,
  onHiba,
}: {
  cim: string;
  lepes: string;
  utmutatoSzoveg: string;
  /** A következő hiányzó rész neve - üresen az elfogadás gombja: "Kész". */
  kovetkezoCimke: string | null;
  onElfogad: (kep: Blob) => void;
  onBezar: () => void;
  onHiba: (uzenet: string) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const onHibaRef = useRef(onHiba);
  const [allapot, setAllapot] = useState<"indul" | "elo" | "ellenorzes">("indul");
  const [kep, setKep] = useState<{ blob: Blob; url: string } | null>(null);

  useEffect(() => {
    onHibaRef.current = onHiba;
  }, [onHiba]);

  // A kamera indítása egyszer; leálláskor a sávok leállnak (a telefon
  // kamera-jelzője kialszik).
  useEffect(() => {
    let el = true;
    if (!navigator.mediaDevices?.getUserMedia) {
      onHibaRef.current("Ez a böngésző nem engedi a beépített kamerát.");
      return;
    }
    navigator.mediaDevices
      .getUserMedia({
        audio: false,
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } },
      })
      .then(async (stream) => {
        if (!el) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        const v = videoRef.current;
        if (v) {
          v.srcObject = stream;
          await v.play().catch(() => undefined);
        }
        setAllapot("elo");
      })
      .catch((e) => el && onHibaRef.current(String(e?.message ?? e)));
    return () => {
      el = false;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };
  }, []);

  // Az elkészült kép URL-je felszabadul, ha már nem kell.
  useEffect(() => {
    if (!kep) return;
    return () => URL.revokeObjectURL(kep.url);
  }, [kep]);

  function exponal() {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const c = document.createElement("canvas");
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    c.getContext("2d")?.drawImage(v, 0, 0, c.width, c.height);
    c.toBlob(
      (blob) => {
        if (!blob) return;
        setKep({ blob, url: URL.createObjectURL(blob) });
        setAllapot("ellenorzes");
      },
      "image/jpeg",
      0.9,
    );
  }

  function ujra() {
    setKep(null);
    setAllapot("elo");
  }

  function elfogad() {
    if (!kep) return;
    onElfogad(kep.blob);
    // Ugyanebben a nézetben jön a következő rész - vissza az élő képre.
    setKep(null);
    setAllapot("elo");
  }

  return (
    <div className="fixed inset-0 z-50 flex touch-manipulation select-none flex-col bg-black text-white">
      {/* Fent: melyik részt fotózza, és honnan. */}
      <div className="absolute inset-x-0 top-0 z-10 bg-gradient-to-b from-black/80 to-transparent px-4 pb-6 pt-[max(env(safe-area-inset-top),12px)]">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[12px] uppercase tracking-wide text-white/70">{lepes}</p>
            <p className="text-[22px] font-semibold leading-tight">{cim}</p>
          </div>
          <button
            type="button"
            onClick={onBezar}
            aria-label="Kamera bezárása"
            className="rounded-full bg-white/15 p-2.5 backdrop-blur"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="mt-1.5 line-clamp-2 text-[13.5px] leading-snug text-white/80">{utmutatoSzoveg}</p>
      </div>

      {/* Az élő kép, vagy ellenőrzéskor az elkészült kép. */}
      <video ref={videoRef} playsInline muted autoPlay className="h-full w-full flex-1 object-cover" />
      {kep && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={kep.url} alt={cim} className="absolute inset-0 h-full w-full object-cover" />
      )}
      {allapot === "indul" && (
        <div className="absolute inset-0 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-white/80" />
        </div>
      )}

      {/* Lent: exponálás, vagy Újra / Következő (= elfogadás). */}
      <div className="absolute inset-x-0 bottom-0 z-10 bg-gradient-to-t from-black/85 to-transparent px-4 pb-[max(env(safe-area-inset-bottom),16px)] pt-10">
        {allapot === "ellenorzes" ? (
          <div className="flex gap-3">
            <button
              type="button"
              onClick={ujra}
              className="flex items-center justify-center gap-2 rounded-2xl bg-white/15 px-5 py-4 text-[16px] font-medium backdrop-blur"
            >
              <RotateCcw className="h-5 w-5" /> Újra
            </button>
            <button
              type="button"
              onClick={elfogad}
              className="flex min-w-0 flex-1 items-center justify-center gap-2 rounded-2xl bg-white px-4 py-4 text-[16px] font-semibold text-black"
            >
              {kovetkezoCimke ? (
                <>
                  <span className="truncate">Következő: {kovetkezoCimke}</span>
                  <ChevronRight className="h-5 w-5 shrink-0" />
                </>
              ) : (
                <>
                  <Check className="h-5 w-5" /> Kész
                </>
              )}
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-center">
            <button
              type="button"
              onClick={exponal}
              disabled={allapot !== "elo"}
              aria-label={`${cim} lefotózása`}
              className="h-[76px] w-[76px] rounded-full border-4 border-white bg-white/90 shadow-lg active:scale-95 disabled:opacity-40"
            />
          </div>
        )}
      </div>
    </div>
  );
}
