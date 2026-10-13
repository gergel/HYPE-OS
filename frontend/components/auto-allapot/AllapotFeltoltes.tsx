"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, Camera, Check, ChevronRight, ImagePlus, Loader2 } from "lucide-react";
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

/** AUTÓ ÁLLAPOTFOTÓK - a bekérő link oldala (a felhasználó kérése).
 *
 * CSAK TELEFONON használják, ezért egy fix, a kijelzőt kitöltő képernyő: nem
 * görget, nem nagyít, nem lötyög (lásd a route viewport-beállítását).
 *
 * A folyamat (mint a MOL Limónál): az autó KÖRVONALA látszik a saját
 * karosszériájával; egy részére nyomva AZONNAL megnyílik a kamera. A fotó
 * után alul ott áll, melyiket fotóztad, és a nagy gomb már a KÖVETKEZŐ
 * hiányzó részt kínálja ("Következő: Jobb oldala") - arra nyomva rögtön jön a
 * következő kamera, így a hét képen végig lehet menni. A feltöltés közben a
 * háttérben fut (több kép párhuzamosan is). Az aznapi újrafotózás lecseréli a
 * korábbi aznapi képet.
 *
 * Egyelőre teszt jelleggel: a linket kézzel küldjük ki, a diszpóval nem megy. */
export function AllapotFeltoltes({ token }: { token: string }) {
  const [adatok, setAdatok] = useState<Adatok | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [folyamatban, setFolyamatban] = useState<Record<string, Feltoltes>>({});
  /** A következő fotózandó rész (a nagy gomb ezt kínálja). */
  const [cel, setCel] = useState<string | null>(null);
  /** Amit legutóbb fotózott - alul ez látszik. */
  const [utolso, setUtolso] = useState<string | null>(null);
  const [elkezdte, setElkezdte] = useState(false);
  const [nev, setNev] = useState(() => {
    try {
      return typeof window === "undefined" ? "" : (window.localStorage.getItem(NEV_TAROLO) ?? "");
    } catch {
      return "";
    }
  });

  const kameraRef = useRef<HTMLInputElement>(null);
  const galeriaRef = useRef<HTMLInputElement>(null);
  // Melyik részhez kértük a képet - a fájlválasztó visszahívása ebből tudja.
  const kertResz = useRef<string | null>(null);
  // A kész / folyamatban lévő részek a "következő" kiszámításához (csak
  // eseménykezelőkben írjuk).
  const foglaltRef = useRef<Set<string>>(new Set());

  // A teljes oldal ne rugózzon / ne húzódjon le (iOS, Android).
  useEffect(() => {
    const html = document.documentElement;
    const regi = [html.style.overscrollBehavior, document.body.style.overscrollBehavior, document.body.style.overflow];
    html.style.overscrollBehavior = "none";
    document.body.style.overscrollBehavior = "none";
    document.body.style.overflow = "hidden";
    return () => {
      [html.style.overscrollBehavior, document.body.style.overscrollBehavior, document.body.style.overflow] = regi;
    };
  }, []);

  const betolt = useCallback(() => {
    fetch(`${API}/${token}`)
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        if (!r.ok) throw new Error(d?.detail ?? `HTTP ${r.status}`);
        const a = d as Adatok;
        foglaltRef.current = new Set(Object.keys(a.mai_fotok));
        setAdatok(a);
        setHiba(null);
        setCel((c) => c ?? OLDAL_SORREND.find((o) => !a.mai_fotok[o]) ?? null);
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
      // privát mód - nem baj
    }
  }

  /** A kamera (vagy galéria) megnyitása egy részhez - a gombnyomás
   * eseményén belül, különben a telefon nem engedi megnyitni. */
  function megnyit(resz: string, galeria = false) {
    kertResz.current = resz;
    setCel(resz);
    setElkezdte(true);
    (galeria ? galeriaRef : kameraRef).current?.click();
  }

  function kovetkezo(utan: string): string | null {
    const i = OLDAL_SORREND.indexOf(utan);
    const sorrend = [...OLDAL_SORREND.slice(i + 1), ...OLDAL_SORREND.slice(0, i + 1)];
    return sorrend.find((o) => !foglaltRef.current.has(o)) ?? null;
  }

  function fajlValasztva(file: File | undefined) {
    const resz = kertResz.current;
    kertResz.current = null;
    if (!file || !resz) return;
    foglaltRef.current.add(resz);
    setUtolso(resz);
    setCel(kovetkezo(resz));
    feltolt(resz, file);
  }

  function feltolt(oldal: string, file: File) {
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
    const hibas = (uzenet: string) => {
      // Ami nem ment fel, az újra fotózandó - visszakerül a sorba.
      foglaltRef.current.delete(oldal);
      setFolyamatban((f) => ({ ...f, [oldal]: { szazalek: 0, hiba: uzenet } }));
      setCel((c) => c ?? oldal);
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
      hibas(uzenet);
    };
    xhr.onerror = () => hibas("Hálózati hiba – fotózd újra.");
    xhr.send(fd);
  }

  // ── Képernyők ──────────────────────────────────────────────────────────────

  const keret = "fixed inset-0 flex flex-col overflow-hidden bg-surface-1 text-text-primary touch-manipulation select-none";

  if (hiba && !adatok) {
    return (
      <div className={`${keret} items-center justify-center px-6 text-center`}>
        <h1 className="mb-2 text-[20px] font-semibold">A link nem él</h1>
        <p className="text-[15px] text-text-secondary">{hiba}</p>
      </div>
    );
  }
  if (!adatok) {
    return (
      <div className={`${keret} items-center justify-center text-text-muted`}>
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  const kar = adatok.karosszeria;
  const cimkek = Object.fromEntries(adatok.oldalak.map((o) => [o.kulcs, reszCimke(o.kulcs, kar, o.cimke)]));
  const kesz = Object.fromEntries(OLDAL_SORREND.map((o) => [o, !!adatok.mai_fotok[o]]));
  const keszDb = OLDAL_SORREND.filter((o) => kesz[o]).length;
  const osszes = OLDAL_SORREND.length;
  const mindKesz = keszDb === osszes;
  const utolsoAllapot = utolso ? folyamatban[utolso] : undefined;
  const fajlInputok = (
    <>
      <input
        ref={kameraRef}
        type="file"
        accept="image/*"
        capture="environment"
        // Nem display:none: egyes iOS-verziók az ilyet programból nem nyitják meg.
        className="pointer-events-none absolute h-px w-px opacity-0"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => {
          fajlValasztva(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <input
        ref={galeriaRef}
        type="file"
        accept="image/*"
        // Nem display:none: egyes iOS-verziók az ilyet programból nem nyitják meg.
        className="pointer-events-none absolute h-px w-px opacity-0"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => {
          fajlValasztva(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
    </>
  );

  // KEZDŐKÉPERNYŐ: név (nem kötelező) + Kezdés - ez már a kamerát nyitja.
  if (!elkezdte && !mindKesz) {
    const elso = cel ?? OLDAL_SORREND[0];
    return (
      <div className={`${keret} px-5 pb-[max(env(safe-area-inset-bottom),16px)] pt-[max(env(safe-area-inset-top),16px)]`}>
        {fajlInputok}
        <div className="shrink-0">
          <p className="text-[12px] uppercase tracking-wide text-text-muted">Autó állapotfotók</p>
          <h1 className="mt-1 text-[26px] font-semibold leading-tight">{adatok.rendszam}</h1>
          {adatok.megnevezes && <p className="text-[15px] text-text-secondary">{adatok.megnevezes}</p>}
        </div>
        <div className="flex min-h-0 flex-1 items-center justify-center py-3">
          <div className="aspect-[260/500] h-full max-h-full max-w-full">
            <AutoKorvonal karosszeria={kar} kesz={kesz} cimkeSzoveg={cimkek} className="h-full w-full" />
          </div>
        </div>
        <div className="shrink-0 space-y-3">
          <p className="text-[15px] leading-snug text-text-secondary">
            {osszes} fotó kell az autóról. A gombra nyomva megnyílik a kamera; minden kép után a következő részt kéri.
            {keszDb > 0 && ` Mára ${keszDb} kép már megvan.`}
          </p>
          <input
            value={nev}
            onChange={(e) => nevMentes(e.target.value)}
            placeholder="A neved (nem kötelező)"
            autoComplete="name"
            className="w-full rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-3 text-[16px] text-text-primary focus:outline-none"
          />
          <button
            type="button"
            onClick={() => megnyit(elso)}
            className="flex w-full items-center justify-center gap-2 rounded-[var(--radius-lg)] bg-bg-accent px-4 py-4 text-[17px] font-semibold text-text-accent"
          >
            <Camera className="h-6 w-6" />
            Kezdés – {cimkek[elso]}
          </button>
        </div>
      </div>
    );
  }

  // FOTÓZÁS KÉPERNYŐ: fejléc · körvonal · alul a lépés és a gombok.
  return (
    <div className={keret}>
      {fajlInputok}
      <header className="shrink-0 px-4 pb-2 pt-[max(env(safe-area-inset-top),12px)]">
        <div className="flex items-baseline justify-between gap-3">
          <p className="min-w-0 truncate text-[18px] font-semibold">
            {adatok.rendszam}
            {adatok.megnevezes && <span className="ml-2 text-[13px] font-normal text-text-muted">{adatok.megnevezes}</span>}
          </p>
          <span className={`shrink-0 text-[15px] font-semibold tabular-nums ${mindKesz ? "text-text-success" : ""}`}>
            {keszDb}/{osszes}
          </span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3">
          <div className="h-full rounded-full bg-text-success transition-all" style={{ width: `${(keszDb / osszes) * 100}%` }} />
        </div>
      </header>

      {/* A KÖRVONAL - egy részére nyomva azonnal a kamera nyílik. */}
      <main className="flex min-h-0 flex-1 items-center justify-center px-4 py-1">
        <div className="aspect-[260/500] h-full max-h-full max-w-full">
          <AutoKorvonal
            karosszeria={kar}
            kesz={kesz}
            kivalasztott={cel}
            onValaszt={(o) => megnyit(o)}
            cimkeSzoveg={cimkek}
            className="h-full w-full"
          />
        </div>
      </main>

      <footer className="shrink-0 space-y-2.5 border-t border-border bg-surface-2 px-4 pb-[max(env(safe-area-inset-bottom),12px)] pt-3">
        {/* Mit fotózott legutóbb, és felment-e. */}
        {utolso && (
          <p className="flex items-center gap-2 text-[14px]">
            {utolsoAllapot?.hiba ? (
              <AlertCircle className="h-4 w-4 shrink-0 text-text-danger" />
            ) : utolsoAllapot ? (
              <Loader2 className="h-4 w-4 shrink-0 animate-spin text-text-muted" />
            ) : (
              <Check className="h-4 w-4 shrink-0 text-text-success" />
            )}
            <span className="min-w-0 truncate">
              Most fotóztad: <b className="font-semibold">{cimkek[utolso]}</b>
              <span className="text-text-muted">
                {utolsoAllapot?.hiba
                  ? " – nem ment fel, fotózd újra"
                  : utolsoAllapot
                    ? utolsoAllapot.szazalek >= 99
                      ? " – mentés…"
                      : ` – feltöltés ${utolsoAllapot.szazalek}%`
                    : " – feltöltve"}
              </span>
            </span>
          </p>
        )}

        {mindKesz ? (
          <div className="rounded-[var(--radius-lg)] bg-surface-3 px-4 py-4 text-center text-[16px] font-semibold text-text-success">
            Köszönjük – mind a {osszes} kép megvan mára.
          </div>
        ) : cel ? (
          <>
            <p className="line-clamp-2 text-[13.5px] leading-snug text-text-secondary">{utmutato(cel, kar)}</p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => megnyit(cel)}
                className="flex min-w-0 flex-1 items-center justify-center gap-2 rounded-[var(--radius-lg)] bg-bg-accent px-4 py-4 text-[17px] font-semibold text-text-accent"
              >
                <Camera className="h-6 w-6 shrink-0" />
                <span className="truncate">
                  {utolso ? "Következő: " : "Fotózás: "}
                  {cimkek[cel]}
                </span>
                {utolso && <ChevronRight className="h-5 w-5 shrink-0" />}
              </button>
              <button
                type="button"
                onClick={() => megnyit(cel, true)}
                aria-label="Kép kiválasztása a galériából"
                className="flex items-center justify-center rounded-[var(--radius-lg)] border border-border px-4 text-text-secondary"
              >
                <ImagePlus className="h-6 w-6" />
              </button>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center gap-2 rounded-[var(--radius-lg)] bg-surface-3 px-4 py-4 text-[15px] text-text-secondary">
            <Loader2 className="h-5 w-5 animate-spin" /> Az utolsó képek feltöltése…
          </div>
        )}

        {/* A hét rész kicsiben - nyomásra az a rész jön (újrafotózás is). */}
        <ul className="grid grid-cols-7 gap-1.5">
          {OLDAL_SORREND.map((o) => {
            const f = adatok.mai_fotok[o];
            const fut = folyamatban[o];
            return (
              <li key={o}>
                <button
                  type="button"
                  onClick={() => megnyit(o)}
                  aria-label={`${cimkek[o]} fotózása`}
                  className={`relative block aspect-square w-full overflow-hidden rounded-[8px] border-2 ${
                    fut?.hiba
                      ? "border-text-danger"
                      : o === cel
                        ? "border-text-blue"
                        : f
                          ? "border-text-success/60"
                          : "border-border"
                  } bg-surface-3`}
                >
                  {f ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={f.belyeg_url} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <Camera className="absolute inset-0 m-auto h-4 w-4 text-text-muted" />
                  )}
                  {fut && !fut.hiba && (
                    <span className="absolute inset-0 flex items-center justify-center bg-black/50">
                      <Loader2 className="h-4 w-4 animate-spin text-white" />
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </footer>
    </div>
  );
}
