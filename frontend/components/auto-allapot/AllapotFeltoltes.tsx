"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, Check, ImagePlus, Loader2 } from "lucide-react";
import { AutoKorvonal, OLDAL_SORREND, reszCimke, utmutato, type Karosszeria } from "@/components/auto-allapot/AutoKorvonal";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1/public/auto-allapot";
const NEV_TAROLO = "hype-auto-allapot-nev";

type Foto = { id: number; oldal: string; keszult_at: string; keszito: string | null; url: string; belyeg_url: string };
type Adatok = {
  rendszam: string;
  megnevezes: string | null;
  karosszeria: Karosszeria;
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
 * Mint a MOL Limónál: az autó KÖRVONALA látszik felülnézetben (a saját
 * karosszériájával - személyautó, SUV vagy kisbusz/furgon), és arra a részére
 * kell rányomni, amelyikről a fotó készül. A kiválasztott résznél útmutató
 * mutatja, honnan kell fotózni; a feltöltés azonnal indul (több rész
 * párhuzamosan is mehet), utána a következő hiányzó rész jön. Hét kép kell:
 * a négy oldal, a csomagtartó (furgonnál a raktér), az első és a hátsó
 * üléssor. Az aznapi újrafotózás lecseréli a korábbi aznapi képet.
 *
 * Egyelőre teszt jelleggel: a linket kézzel küldjük ki, a diszpóval nem megy. */
export function AllapotFeltoltes({ token }: { token: string }) {
  const [adatok, setAdatok] = useState<Adatok | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState<Record<string, Feltoltes>>({});
  const [kivalasztott, setKivalasztott] = useState<string | null>(null);
  // A mai képek legfrissebb állapota a feltöltés-visszahívásoknak (a
  // következő hiányzó rész kiszámításához) - csak eseménykezelőben írjuk.
  const maiRef = useRef<Record<string, Foto>>({});
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
        const a = d as Adatok;
        maiRef.current = a.mai_fotok;
        setAdatok(a);
        setHiba(null);
        // Az első hiányzó résszel indulunk.
        setKivalasztott((k) => k ?? OLDAL_SORREND.find((o) => !a.mai_fotok[o]) ?? OLDAL_SORREND[0]);
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
        maiRef.current = { ...maiRef.current, [oldal]: foto };
        const mai = maiRef.current;
        setAdatok((a) => (a ? { ...a, mai_fotok: { ...a.mai_fotok, [oldal]: foto } } : a));
        // Ha még ezen a részen állt, ugorjon a következő hiányzóra.
        setKivalasztott((k) => (k === oldal ? OLDAL_SORREND.find((o) => !mai[o]) ?? oldal : k));
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

  const kar = adatok.karosszeria;
  const cimkek = Object.fromEntries(adatok.oldalak.map((o) => [o.kulcs, reszCimke(o.kulcs, kar, o.cimke)]));
  const kesz = Object.fromEntries(OLDAL_SORREND.map((o) => [o, !!adatok.mai_fotok[o]]));
  const keszDb = OLDAL_SORREND.filter((o) => kesz[o]).length;
  const osszes = OLDAL_SORREND.length;
  const sel = kivalasztott ?? OLDAL_SORREND[0];
  const selFoto = adatok.mai_fotok[sel];
  const selFut = folyamatban[sel];
  const selSzam = OLDAL_SORREND.indexOf(sel) + 1;

  return (
    <div className="min-h-screen bg-surface-1 px-4 pb-28 pt-6 text-text-primary sm:pb-16">
      <div className="mx-auto max-w-2xl">
        <p className="text-[12px] uppercase tracking-wide text-text-muted">Autó állapotfotók</p>
        <h1 className="mt-1 text-[24px] font-semibold">{adatok.rendszam}</h1>
        {adatok.megnevezes && <p className="text-[14px] text-text-secondary">{adatok.megnevezes}</p>}

        <div
          className={`mt-4 rounded-[var(--radius-lg)] border px-4 py-3 text-[14px] ${
            keszDb === osszes ? "border-text-success/40 bg-surface-2 text-text-success" : "border-border bg-surface-2"
          }`}
        >
          {keszDb === osszes ? `Köszönjük – mind a ${osszes} kép megvan mára.` : `Mára ${keszDb} / ${osszes} kép kész.`}
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3">
            <div className="h-full rounded-full bg-text-success transition-all" style={{ width: `${(keszDb / osszes) * 100}%` }} />
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] sm:items-start">
          {/* A KÖRVONAL: arra a részére kell rányomni, amelyikről fotózol. */}
          <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-3">
            <p className="mb-1 text-center text-[13px] text-text-secondary">
              Koppints az autó azon részére, amelyikről fotót töltesz fel.
            </p>
            <AutoKorvonal
              karosszeria={kar}
              kesz={kesz}
              kivalasztott={sel}
              onValaszt={setKivalasztott}
              cimkeSzoveg={cimkek}
              className="mx-auto block w-full max-w-[230px] sm:max-w-[300px]"
            />
          </div>

          {/* A KIVÁLASZTOTT RÉSZ: útmutató + fotózás */}
          <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
            <p className="text-[12px] uppercase tracking-wide text-text-muted">
              {selSzam}. / {osszes} rész
            </p>
            <div className="mt-0.5 flex items-center justify-between gap-2">
              <h2 className="text-[19px] font-semibold">{cimkek[sel]}</h2>
              {selFoto && (
                <span className="flex items-center gap-1 text-[13px] text-text-success">
                  <Check className="h-4 w-4" /> {ido(selFoto.keszult_at)}
                </span>
              )}
            </div>
            <div className="mt-3 flex items-start gap-3">
              <AutoKorvonal karosszeria={kar} kamera={sel} cimkek={false} kivalasztott={sel} className="w-[92px] shrink-0" />
              <p className="text-[14px] leading-relaxed text-text-secondary">{utmutato(sel, kar)}</p>
            </div>

            {(selFoto || (selFut && !selFut.hiba)) && (
              <div className="relative mt-3 overflow-hidden rounded-[var(--radius)] bg-surface-3">
                {selFoto ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={selFoto.belyeg_url} alt={cimkek[sel]} className="aspect-[4/3] w-full object-cover" />
                ) : (
                  <div className="aspect-[4/3]" />
                )}
                {selFut && !selFut.hiba && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/50 text-[13px] text-white">
                    <Loader2 className="h-6 w-6 animate-spin" />
                    {selFut.szazalek >= 99 ? "Mentés…" : `${selFut.szazalek}%`}
                  </div>
                )}
              </div>
            )}
            {selFut?.hiba && <p className="mt-2 text-[13px] text-text-danger">{selFut.hiba}</p>}

            <div className="mt-3 hidden gap-2 sm:flex">
              <label className="flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-[var(--radius)] bg-bg-accent px-3 py-3 text-[15px] font-medium text-text-accent">
                <Camera className="h-5 w-5" />
                {selFoto ? "Újrafotózás" : "Fotózás"}
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  disabled={!!selFut && !selFut.hiba}
                  onChange={(e) => {
                    feltolt(sel, e.target.files?.[0]);
                    e.target.value = "";
                  }}
                />
              </label>
              <label
                title="Kép kiválasztása a galériából"
                className="flex cursor-pointer items-center justify-center rounded-[var(--radius)] border border-border px-3 py-3 text-text-secondary"
              >
                <ImagePlus className="h-5 w-5" />
                <span className="sr-only">Kép kiválasztása a galériából</span>
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  disabled={!!selFut && !selFut.hiba}
                  onChange={(e) => {
                    feltolt(sel, e.target.files?.[0]);
                    e.target.value = "";
                  }}
                />
              </label>
            </div>
          </div>
        </div>

        {/* Az összes rész egy sorban - koppintásra oda ugrik. */}
        <ul className="mt-4 grid grid-cols-4 gap-2 sm:grid-cols-7">
          {OLDAL_SORREND.map((o) => {
            const f = adatok.mai_fotok[o];
            const fut = folyamatban[o];
            return (
              <li key={o}>
                <button
                  type="button"
                  onClick={() => setKivalasztott(o)}
                  className={`w-full overflow-hidden rounded-[var(--radius)] border text-left ${
                    o === sel ? "border-text-accent" : f ? "border-text-success/50" : "border-border"
                  }`}
                >
                  <div className="relative flex aspect-square items-center justify-center bg-surface-3 text-text-muted">
                    {f ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={f.belyeg_url} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <Camera className="h-4 w-4" />
                    )}
                    {fut && !fut.hiba && (
                      <span className="absolute inset-0 flex items-center justify-center bg-black/50">
                        <Loader2 className="h-4 w-4 animate-spin text-white" />
                      </span>
                    )}
                  </div>
                  <p className="truncate px-1.5 py-1 text-[11px] text-text-secondary">{cimkek[o]}</p>
                </button>
              </li>
            );
          })}
        </ul>

        <label className="mt-5 flex flex-col gap-1 text-[12.5px] text-text-muted">
          A neved (nem kötelező)
          <input
            value={nev}
            onChange={(e) => nevMentes(e.target.value)}
            placeholder="Pl. Kovács Péter"
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2 text-[15px] text-text-primary focus:outline-none"
          />
        </label>
      </div>

      {/* TELEFONON: a fotózás gombja mindig kéznél, az alján rögzítve. */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface-1/95 px-4 py-3 backdrop-blur sm:hidden">
        <div className="mx-auto flex max-w-2xl items-center gap-2">
          <p className="min-w-0 flex-1 truncate text-[14px] font-medium">
            {selSzam}/{osszes} · {cimkek[sel]}
          </p>
          <label className="flex cursor-pointer items-center justify-center gap-2 rounded-[var(--radius)] bg-bg-accent px-4 py-3 text-[15px] font-medium text-text-accent">
            <Camera className="h-5 w-5" />
            {selFoto ? "Újra" : "Fotózás"}
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              disabled={!!selFut && !selFut.hiba}
              onChange={(e) => {
                feltolt(sel, e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </label>
          <label
            title="Kép kiválasztása a galériából"
            className="flex cursor-pointer items-center justify-center rounded-[var(--radius)] border border-border px-3 py-3 text-text-secondary"
          >
            <ImagePlus className="h-5 w-5" />
            <span className="sr-only">Kép kiválasztása a galériából</span>
            <input
              type="file"
              accept="image/*"
              className="hidden"
              disabled={!!selFut && !selFut.hiba}
              onChange={(e) => {
                feltolt(sel, e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </div>
    </div>
  );
}
