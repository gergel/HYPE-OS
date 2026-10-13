"use client";

import { useCallback, useEffect, useState } from "react";
import { Camera, Check, ImagePlus, Loader2 } from "lucide-react";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1/public/auto-allapot";
const NEV_TAROLO = "hype-auto-allapot-nev";

type Foto = { id: number; oldal: string; keszult_at: string; keszito: string | null; url: string; belyeg_url: string };
type Adatok = {
  rendszam: string;
  megnevezes: string | null;
  ma: string;
  oldalak: { kulcs: string; cimke: string }[];
  mai_fotok: Record<string, Foto>;
};
type Feltoltes = { szazalek: number; hiba?: string };

function ido(iso: string): string {
  return new Date(iso).toLocaleTimeString("hu-HU", { hour: "2-digit", minute: "2-digit" });
}

/** AUTÓ ÁLLAPOTFOTÓK - a bekérő link oldala (a felhasználó kérése).
 *
 * Hét kép kell az autóról: a négy oldaláról egy-egy, a csomagtartó, az első
 * és a hátsó üléssor. Mindegyik helyre egy gombnyomással fotózható (telefonon
 * a kamera nyílik meg) vagy a galériából választható kép; a feltöltés azonnal
 * indul, a hét hely egymástól függetlenül (párhuzamosan) is mehet. Ha egy
 * nézetet aznap újrafotóznak, az új kép lecseréli az aznapit.
 *
 * Egyelőre teszt jelleggel: a linket kézzel küldjük ki, a diszpóval nem megy. */
export function AllapotFeltoltes({ token }: { token: string }) {
  const [adatok, setAdatok] = useState<Adatok | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState<Record<string, Feltoltes>>({});
  const [nev, setNev] = useState(() => {
    try {
      return typeof window === "undefined" ? "" : (window.localStorage.getItem(NEV_TAROLO) ?? "");
    } catch {
      return "";
    }
  });

  const betolt = useCallback(() => {
    fetch(`${API}/${token}`)
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        if (!r.ok) throw new Error(d?.detail ?? `HTTP ${r.status}`);
        setAdatok(d as Adatok);
        setHiba(null);
      })
      .catch((e) => setHiba(String(e?.message ?? e)));
  }, [token]);

  useEffect(() => {
    betolt();
  }, [betolt]);

  function nevMentes(uj: string) {
    setNev(uj);
    try {
      window.localStorage.setItem(NEV_TAROLO, uj);
    } catch {
      // privát mód - nem baj, csak legközelebb újra be kell írni
    }
  }

  function feltolt(oldal: string, file: File | undefined) {
    if (!file) return;
    setFolyamatban((f) => ({ ...f, [oldal]: { szazalek: 0 } }));
    const fd = new FormData();
    fd.append("oldal", oldal);
    if (nev.trim()) fd.append("keszito", nev.trim());
    fd.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API}/${token}/foto`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable)
        setFolyamatban((f) => ({ ...f, [oldal]: { szazalek: Math.min(99, Math.round((e.loaded / e.total) * 100)) } }));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const foto = JSON.parse(xhr.responseText) as Foto;
        setAdatok((a) => (a ? { ...a, mai_fotok: { ...a.mai_fotok, [oldal]: foto } } : a));
        setFolyamatban((f) => {
          const uj = { ...f };
          delete uj[oldal];
          return uj;
        });
        return;
      }
      let uzenet = `Sikertelen feltöltés (${xhr.status})`;
      try {
        uzenet = JSON.parse(xhr.responseText).detail || uzenet;
      } catch {
        // nem JSON válasz
      }
      setFolyamatban((f) => ({ ...f, [oldal]: { szazalek: 0, hiba: uzenet } }));
    };
    xhr.onerror = () =>
      setFolyamatban((f) => ({ ...f, [oldal]: { szazalek: 0, hiba: "Hálózati hiba – próbáld újra." } }));
    xhr.send(fd);
  }

  if (hiba && !adatok) {
    return (
      <div className="min-h-screen bg-surface-1 px-4 py-16 text-center text-text-primary">
        <h1 className="mb-2 text-[20px] font-semibold">A link nem él</h1>
        <p className="text-[14px] text-text-secondary">{hiba}</p>
      </div>
    );
  }
  if (!adatok) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-1 text-text-muted">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  const kesz = adatok.oldalak.filter((o) => adatok.mai_fotok[o.kulcs]).length;
  const osszes = adatok.oldalak.length;

  return (
    <div className="min-h-screen bg-surface-1 px-4 pb-16 pt-6 text-text-primary">
      <div className="mx-auto max-w-2xl">
        <p className="text-[12px] uppercase tracking-wide text-text-muted">Autó állapotfotók</p>
        <h1 className="mt-1 text-[24px] font-semibold">{adatok.rendszam}</h1>
        {adatok.megnevezes && <p className="text-[14px] text-text-secondary">{adatok.megnevezes}</p>}
        <p className="mt-3 text-[14px] leading-relaxed text-text-secondary">
          Kérjük, készíts {osszes} fotót az autóról: a négy oldaláról egyet-egyet, a csomagtartóról, az első és a
          hátsó üléssorról. Minden képet a saját helyére tölts fel – telefonon a gomb a kamerát nyitja meg.
        </p>

        <label className="mt-4 flex flex-col gap-1 text-[12.5px] text-text-muted">
          A neved (nem kötelező)
          <input
            value={nev}
            onChange={(e) => nevMentes(e.target.value)}
            placeholder="Pl. Kovács Péter"
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2 text-[15px] text-text-primary focus:outline-none"
          />
        </label>

        <div
          className={`mt-5 rounded-[var(--radius-lg)] border px-4 py-3 text-[14px] ${
            kesz === osszes ? "border-text-success/40 bg-surface-2 text-text-success" : "border-border bg-surface-2"
          }`}
        >
          {kesz === osszes
            ? `Köszönjük – mind a ${osszes} kép megvan mára.`
            : `Mára ${kesz} / ${osszes} kép kész.`}
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3">
            <div className="h-full rounded-full bg-text-success transition-all" style={{ width: `${(kesz / osszes) * 100}%` }} />
          </div>
        </div>

        <ul className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {adatok.oldalak.map((o) => {
            const foto = adatok.mai_fotok[o.kulcs];
            const fut = folyamatban[o.kulcs];
            return (
              <li key={o.kulcs} className="overflow-hidden rounded-[var(--radius-lg)] border border-border bg-surface-2">
                <div className="relative aspect-[4/3] bg-surface-3">
                  {foto ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={foto.belyeg_url} alt={o.cimke} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-text-muted">
                      <Camera className="h-8 w-8" />
                    </div>
                  )}
                  {fut && !fut.hiba && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/50 text-[13px] text-white">
                      <Loader2 className="h-6 w-6 animate-spin" />
                      {fut.szazalek >= 99 ? "Mentés…" : `${fut.szazalek}%`}
                    </div>
                  )}
                </div>
                <div className="space-y-2 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-[15px] font-medium">{o.cimke}</p>
                    {foto && (
                      <span className="flex items-center gap-1 text-[12.5px] text-text-success">
                        <Check className="h-4 w-4" />
                        {ido(foto.keszult_at)}
                      </span>
                    )}
                  </div>
                  {fut?.hiba && <p className="text-[12.5px] text-text-danger">{fut.hiba}</p>}
                  <div className="flex gap-2">
                    <label className="flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-[var(--radius)] bg-bg-accent px-3 py-2.5 text-[14px] font-medium text-text-accent">
                      <Camera className="h-4 w-4" />
                      {foto ? "Újrafotózás" : "Fotózás"}
                      <input
                        type="file"
                        accept="image/*"
                        capture="environment"
                        className="hidden"
                        disabled={!!fut && !fut.hiba}
                        onChange={(e) => {
                          feltolt(o.kulcs, e.target.files?.[0]);
                          e.target.value = "";
                        }}
                      />
                    </label>
                    <label
                      title="Kép kiválasztása a galériából"
                      className="flex cursor-pointer items-center justify-center rounded-[var(--radius)] border border-border px-3 py-2.5 text-text-secondary"
                    >
                      <ImagePlus className="h-4 w-4" />
                      <span className="sr-only">Kép kiválasztása a galériából</span>
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        disabled={!!fut && !fut.hiba}
                        onChange={(e) => {
                          feltolt(o.kulcs, e.target.files?.[0]);
                          e.target.value = "";
                        }}
                      />
                    </label>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
