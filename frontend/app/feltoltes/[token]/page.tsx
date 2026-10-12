"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { Folder as FolderIcon, FolderPlus, Image as ImageIcon, Loader2, Trash2, Upload, Video, X } from "lucide-react";
import {
  feltoltesFajl,
  feltoltesMappa,
  feltoltesTorles,
  getFeltoltesAdatok,
  type FeltoltesAdatok,
  type FeltoltesFajl,
} from "@/lib/portalApi";

/** Ennyi fájl megy fel egyszerre (a többi sorban vár). */
const PARHUZAMOS = 3;

type SorElem = {
  azon: number;
  nev: string;
  meret: number;
  folderId: number | null;
  folderNev: string;
  allapot: "var" | "fut" | "kesz" | "hiba" | "megszakitva";
  szazalek: number;
  hiba?: string;
};

function meretSzoveg(b: number): string {
  if (b >= 1024 ** 3) return `${(b / 1024 ** 3).toFixed(1)} GB`;
  if (b >= 1024 ** 2) return `${(b / 1024 ** 2).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(b / 1024))} KB`;
}

/** A PORTÁL FELTÖLTŐ LINKJÉNEK oldala (a felhasználó kérése).
 *
 * Akinek ezt a linket küldjük, az bejelentkezés nélkül tud mappát létrehozni
 * és fájlokat feltölteni a portálra (vagy csak a kijelölt mappájába), és nem
 * lát bele az admin felületbe. A token maga a belépő; visszavonása után az
 * oldal nem él tovább (lásd backend portal_public.py "feltoltes" végpontjai).
 *
 * PÁRHUZAMOS FELTÖLTÉS (a felhasználó kérése): a feltöltés nem zárja le az
 * oldalt - közben új mappa hozható létre, és oda is indítható feltöltés; a
 * fájlok egy közös sorban, egyszerre többen haladnak, mindegyik a saját
 * haladásával, és egyenként megszakíthatók.
 *
 * SAJÁT FÁJLOK (a felhasználó kérése): mindenki csak azt látja, amit ő
 * töltött fel (ez a böngésző), és abból törölni is tud - a szerver a böngésző
 * azonosítója alapján dönt (lásd lib/portalApi.feltoltoKulcs).
 *
 * A megjelenés az admin "Tartalom" feltöltő-zónáját követi (szaggatott
 * húzd-ide sáv, lucide ikonok) - ugyanaz a design-nyelv, emoji nélkül. */
export default function FeltoltesPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [adatok, setAdatok] = useState<FeltoltesAdatok | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [ujMappaNyitva, setUjMappaNyitva] = useState(false);
  const [ujMappa, setUjMappa] = useState("");
  const [mappaKeszul, setMappaKeszul] = useState(false);
  const [dragCel, setDragCel] = useState<number | "root" | null>(null);
  const [sor, setSor] = useState<SorElem[]>([]);
  const [torlesFolyik, setTorlesFolyik] = useState<string | null>(null);

  // A feltöltési sor vezérlése ref-ekben (a React-állapot csak a kijelzés).
  const varakozok = useRef<{ azon: number; file: File; folderId: number | null }[]>([]);
  const futok = useRef(new Map<number, () => void>());
  const kovetkezoAzon = useRef(1);

  const betolt = useCallback(() => {
    getFeltoltesAdatok(token)
      .then((a) => {
        setAdatok(a);
        setHiba(null);
      })
      .catch((e) => setHiba(String(e?.message ?? e)));
  }, [token]);

  useEffect(() => {
    betolt();
  }, [betolt]);

  const aktiv = sor.some((s) => s.allapot === "var" || s.allapot === "fut");

  // Futó feltöltés közben az oldal elhagyása előtt figyelmeztetünk.
  useEffect(() => {
    if (!aktiv) return;
    const figyelmeztet = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", figyelmeztet);
    return () => window.removeEventListener("beforeunload", figyelmeztet);
  }, [aktiv]);

  function frissit(azon: number, valtozas: Partial<SorElem>) {
    setSor((s) => s.map((x) => (x.azon === azon ? { ...x, ...valtozas } : x)));
  }

  function indit() {
    while (futok.current.size < PARHUZAMOS && varakozok.current.length > 0) {
      const { azon, file, folderId } = varakozok.current.shift()!;
      frissit(azon, { allapot: "fut", szazalek: 0 });
      const { kesz, megszakit } = feltoltesFajl(token, file, folderId, (p) => frissit(azon, { szazalek: p }));
      futok.current.set(azon, megszakit);
      void kesz.then((e) => {
        futok.current.delete(azon);
        if (e.ok) {
          frissit(azon, { allapot: "kesz", szazalek: 100 });
          betolt();
        } else {
          frissit(azon, { allapot: e.megszakitva ? "megszakitva" : "hiba", hiba: e.hiba });
        }
        indit();
      });
    }
  }

  function sorba(files: FileList | File[] | null, folderId: number | null) {
    const lista = files ? Array.from(files) : [];
    if (lista.length === 0) return;
    const folderNev =
      folderId == null ? "Mappa nélkül" : adatok?.folders.find((f) => f.id === folderId)?.name ?? "Mappa";
    const ujak: SorElem[] = lista.map((file) => {
      const azon = kovetkezoAzon.current++;
      varakozok.current.push({ azon, file, folderId });
      return { azon, nev: file.name, meret: file.size, folderId, folderNev, allapot: "var", szazalek: 0 };
    });
    setSor((s) => [...s, ...ujak]);
    indit();
  }

  function megszakit(azon: number) {
    const abort = futok.current.get(azon);
    if (abort) {
      abort();
      return;
    }
    varakozok.current = varakozok.current.filter((v) => v.azon !== azon);
    frissit(azon, { allapot: "megszakitva", hiba: "Megszakítva." });
  }

  async function mappaLetrehozas() {
    if (!ujMappa.trim()) return;
    setMappaKeszul(true);
    try {
      await feltoltesMappa(token, ujMappa.trim());
      setUjMappa("");
      setUjMappaNyitva(false);
      betolt();
    } catch (e) {
      alert(String((e as Error)?.message ?? e));
    } finally {
      setMappaKeszul(false);
    }
  }

  async function torles(mit: "video" | "kep" | "mappa", id: number, nev: string) {
    const kerdes =
      mit === "mappa"
        ? `Törlöd a(z) „${nev}” mappát és a benne lévő saját feltöltéseidet?`
        : `Törlöd: „${nev}”? Ezt nem lehet visszavonni.`;
    if (!window.confirm(kerdes)) return;
    setTorlesFolyik(`${mit}:${id}`);
    try {
      await feltoltesTorles(token, mit, id);
      betolt();
    } catch (e) {
      alert(String((e as Error)?.message ?? e));
    } finally {
      setTorlesFolyik(null);
    }
  }

  /** Húzd-ide kezelés: a cél (fő zóna vagy mappa) az elem data-cel
   * attribútumából jön ("root" vagy a mappa azonosítója). */
  function celje(el: HTMLElement): number | "root" {
    const c = el.dataset.cel;
    return c === "root" || !c ? "root" : Number(c);
  }
  function huzasFelett(e: React.DragEvent<HTMLElement>) {
    e.preventDefault();
    setDragCel(celje(e.currentTarget));
  }
  function huzasEl(e: React.DragEvent<HTMLElement>) {
    const cel = celje(e.currentTarget);
    setDragCel((d) => (d === cel ? null : d));
  }
  function ejtes(e: React.DragEvent<HTMLElement>) {
    e.preventDefault();
    setDragCel(null);
    const cel = celje(e.currentTarget);
    sorba(e.dataTransfer.files, cel === "root" ? null : cel);
  }

  if (hiba && !adatok) {
    return (
      <div className="hype-portal dark grain min-h-screen bg-ink text-bone">
        <main className="mx-auto max-w-xl px-6 py-20 text-center">
          <h1 className="mb-2 font-display text-2xl text-bone">A feltöltő link nem él</h1>
          <p className="text-mist">{hiba}</p>
        </main>
      </div>
    );
  }
  if (!adatok) {
    return (
      <div className="hype-portal dark grain min-h-screen bg-ink text-bone">
        <main className="flex min-h-screen items-center justify-center">
          <span className="font-mono text-xs uppercase tracking-eyebrow text-mist">Betöltés…</span>
        </main>
      </div>
    );
  }

  const fajlokMappaban = (folderId: number | null) => adatok.fajlok.filter((f) => f.folder_id === folderId);
  const mappaNelkul = adatok.csak_mappa ? [] : fajlokMappaban(null);
  const futoDb = sor.filter((s) => s.allapot === "fut").length;
  const varoDb = sor.filter((s) => s.allapot === "var").length;
  const lezartDb = sor.filter((s) => s.allapot !== "fut" && s.allapot !== "var").length;

  return (
    <div className="hype-portal dark grain min-h-screen bg-ink text-bone">
      {/* RAGADÓS fejléc a portál nevével (a felhasználó kérése): telefonon,
          hosszú mappalistában görgetve is mindig látszik, hova tölt fel az
          ember - és az is, ha épp fut feltöltés. */}
      <div className="sticky top-0 z-40 border-b border-ink-line bg-ink/95 px-6 py-2.5 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
          <p className="truncate text-sm text-bone">
            <span className="mr-2 font-mono text-[11px] uppercase tracking-eyebrow text-mist">Feltöltés ide:</span>
            {adatok.title}
          </p>
          {aktiv && (
            <span className="flex shrink-0 items-center gap-1.5 font-mono text-[11px] uppercase tracking-eyebrow text-mist">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {futoDb} fut{varoDb > 0 ? ` · ${varoDb} vár` : ""}
            </span>
          )}
        </div>
      </div>
      <main className="mx-auto max-w-3xl px-6 py-10">
        <p className="mb-1 font-mono text-xs uppercase tracking-eyebrow text-mist">Fájl-feltöltés</p>
        <h1 className="mb-2 break-words font-display text-3xl text-bone">{adatok.title}</h1>
        <p className="mb-8 text-sm leading-relaxed text-mist">
          Ezen az oldalon mappákba rendezve tölthetsz fel videókat és képeket – egyszerre több mappába is, a
          feltöltések párhuzamosan haladnak. Csak a saját feltöltéseidet látod, és azokat törölheted is.
        </p>

        {/* A FELTÖLTÉSI SOR: minden fájl a saját haladásával. */}
        {sor.length > 0 && (
          <section className="mb-6 rounded-2xl border border-ink-line bg-ink-card px-4 py-3">
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="font-mono text-[11px] uppercase tracking-eyebrow text-mist">Feltöltések</p>
              {lezartDb > 0 && (
                <button
                  type="button"
                  onClick={() => setSor((s) => s.filter((x) => x.allapot === "fut" || x.allapot === "var"))}
                  className="text-xs text-mist underline-offset-2 hover:text-bone hover:underline"
                >
                  Befejezettek elrejtése
                </button>
              )}
            </div>
            <ul className="space-y-2.5">
              {sor.map((s) => (
                <li key={s.azon} className="text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <p className="min-w-0 truncate text-bone">
                      {s.nev}
                      <span className="ml-2 text-xs text-mist">
                        → {s.folderNev} · {meretSzoveg(s.meret)}
                      </span>
                    </p>
                    <div className="flex shrink-0 items-center gap-2 text-xs">
                      <span
                        className={
                          s.allapot === "kesz"
                            ? "text-emerald-400"
                            : s.allapot === "hiba"
                              ? "text-red-400"
                              : "text-mist"
                        }
                      >
                        {s.allapot === "var"
                          ? "Vár…"
                          : s.allapot === "fut"
                            ? s.szazalek >= 99
                              ? "Mentés…"
                              : `${s.szazalek}%`
                            : s.allapot === "kesz"
                              ? "Kész"
                              : s.allapot === "megszakitva"
                                ? "Megszakítva"
                                : "Hiba"}
                      </span>
                      {(s.allapot === "var" || s.allapot === "fut") && (
                        <button
                          type="button"
                          onClick={() => megszakit(s.azon)}
                          title="Feltöltés megszakítása"
                          aria-label={`${s.nev} feltöltésének megszakítása`}
                          className="rounded-lg p-1 text-mist transition hover:bg-ink hover:text-bone"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                  {(s.allapot === "fut" || s.allapot === "var") && (
                    <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-ink-line">
                      <div className="h-full rounded-full bg-bone/70 transition-all" style={{ width: `${s.szazalek}%` }} />
                    </div>
                  )}
                  {s.allapot === "hiba" && s.hiba && <p className="mt-1 text-xs text-red-400">{s.hiba}</p>}
                </li>
              ))}
            </ul>
            {sor.some((s) => s.allapot === "kesz") && (
              <p className="mt-3 text-xs text-mist">A videók feldolgozása a feltöltés után pár percet vehet igénybe.</p>
            )}
          </section>
        )}

        {/* Fejléc: Tartalom + Új mappa - ugyanaz a minta, mint az adminon. */}
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="font-display text-xl text-bone">Tartalom</h2>
          {!adatok.csak_mappa && (
            <button
              type="button"
              onClick={() => setUjMappaNyitva((n) => !n)}
              className="flex items-center gap-2 rounded-xl border border-ink-line px-3.5 py-2 text-sm text-bone transition hover:border-bone/40"
            >
              <FolderPlus className="h-4 w-4" />
              Új mappa
            </button>
          )}
        </div>
        {!adatok.csak_mappa && (
          <p className="mb-4 text-sm text-mist">
            Nyiss meg egy mappát, vagy tölts fel ide videókat és képeket mappa nélkül. Feltöltés közben is
            létrehozhatsz új mappát, és oda is indíthatsz feltöltést.
          </p>
        )}

        {ujMappaNyitva && (
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <input
              value={ujMappa}
              onChange={(e) => setUjMappa(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void mappaLetrehozas()}
              placeholder="Új mappa neve…"
              autoFocus
              className="min-w-0 flex-1 rounded-xl border border-ink-line bg-transparent px-3.5 py-2 text-sm text-bone placeholder:text-mist focus:border-bone/40 focus:outline-none"
            />
            <button
              type="button"
              onClick={mappaLetrehozas}
              disabled={mappaKeszul || !ujMappa.trim()}
              className="rounded-xl border border-ink-line px-3.5 py-2 text-sm text-bone transition hover:border-bone/40 disabled:opacity-50"
            >
              Létrehozás
            </button>
          </div>
        )}

        {/* A fő feltöltő-zóna: húzd ide, vagy kattints a tallózáshoz. */}
        {!adatok.csak_mappa && (
          <label
            data-cel="root"
            onDragOver={huzasFelett}
            onDragLeave={huzasEl}
            onDrop={ejtes}
            className={`mb-3 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-3xl border-2 border-dashed px-6 py-12 text-center transition ${
              dragCel === "root" ? "border-bone/70 bg-ink-card" : "border-ink-line hover:border-bone/40"
            }`}
          >
            <Upload className="h-6 w-6 text-mist" />
            <span className="text-base text-bone">Húzd ide a fájlokat</span>
            <span className="text-sm text-mist">Vagy kattints a tallózáshoz – videók és képek mehetnek.</span>
            <input
              type="file"
              multiple
              accept="video/*,image/*"
              className="hidden"
              onChange={(e) => {
                sorba(e.target.files, null);
                e.target.value = "";
              }}
            />
          </label>
        )}
        {mappaNelkul.length > 0 && (
          <div className="mb-6">
            <p className="mb-1.5 font-mono text-[11px] uppercase tracking-eyebrow text-mist">Mappa nélkül feltöltve</p>
            <SajatFajlok fajlok={mappaNelkul} torlesFolyik={torlesFolyik} onTorles={torles} />
          </div>
        )}

        {/* Mappák: mindegyik saját húzd-ide céllal, feltöltés gombbal és a
            benne lévő SAJÁT feltöltésekkel. */}
        <div className="mt-6 space-y-3">
          {adatok.folders.length === 0 && (
            <p className="text-sm text-mist">
              {adatok.csak_mappa ? "A kijelölt mappa nem található." : "Még nincs mappa – hozz létre egyet fent."}
            </p>
          )}
          {adatok.folders.map((f) => {
            const sajatFajlok = fajlokMappaban(f.id);
            return (
              <div
                key={f.id}
                data-cel={f.id}
                onDragOver={huzasFelett}
                onDragLeave={huzasEl}
                onDrop={ejtes}
                className={`rounded-2xl border px-4 py-3.5 transition ${
                  dragCel === f.id ? "border-bone/70 bg-ink-card" : "border-ink-line"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <FolderIcon className="h-5 w-5 shrink-0 text-mist" />
                    <div className="min-w-0">
                      <p className="truncate text-base text-bone">{f.name || "Névtelen mappa"}</p>
                      <p className="font-mono text-[11px] uppercase tracking-eyebrow text-mist">
                        Saját: {f.video_db} videó · {f.kep_db} kép
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {f.sajat && (
                      <button
                        type="button"
                        onClick={() => void torles("mappa", f.id, f.name)}
                        disabled={torlesFolyik === `mappa:${f.id}`}
                        title="A mappa törlése"
                        aria-label={`${f.name} mappa törlése`}
                        className="rounded-xl border border-ink-line p-2 text-mist transition hover:border-bone/40 hover:text-bone disabled:opacity-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                    <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-ink-line px-3.5 py-2 text-sm text-bone transition hover:border-bone/40">
                      <Upload className="h-4 w-4" />
                      Feltöltés ide
                      <input
                        type="file"
                        multiple
                        accept="video/*,image/*"
                        className="hidden"
                        onChange={(e) => {
                          sorba(e.target.files, f.id);
                          e.target.value = "";
                        }}
                      />
                    </label>
                  </div>
                </div>
                {sajatFajlok.length > 0 && (
                  <div className="mt-3 border-t border-ink-line pt-3">
                    <SajatFajlok fajlok={sajatFajlok} torlesFolyik={torlesFolyik} onTorles={torles} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </main>
    </div>
  );
}

/** A SAJÁT feltöltések listája törlés-gombbal. */
function SajatFajlok({
  fajlok,
  torlesFolyik,
  onTorles,
}: {
  fajlok: FeltoltesFajl[];
  torlesFolyik: string | null;
  onTorles: (mit: "video" | "kep", id: number, nev: string) => void;
}) {
  return (
    <ul className="space-y-1.5">
      {fajlok.map((f) => {
        const kulcs = `${f.tipus}:${f.id}`;
        return (
          <li key={kulcs} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex min-w-0 items-center gap-2">
              {f.thumbnail_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={f.thumbnail_url} alt="" className="h-8 w-12 shrink-0 rounded object-cover" />
              ) : f.tipus === "video" ? (
                <Video className="h-4 w-4 shrink-0 text-mist" />
              ) : (
                <ImageIcon className="h-4 w-4 shrink-0 text-mist" />
              )}
              <span className="min-w-0 truncate text-bone">{f.title}</span>
              <span className="shrink-0 text-xs text-mist">
                {f.size_bytes > 0 ? meretSzoveg(f.size_bytes) : ""}
                {f.tipus === "video" && f.status === "processing" ? " · feldolgozás alatt" : ""}
                {f.tipus === "video" && f.status === "failed" ? " · feldolgozási hiba" : ""}
              </span>
            </span>
            <button
              type="button"
              onClick={() => onTorles(f.tipus, f.id, f.title)}
              disabled={torlesFolyik === kulcs}
              title="Törlés"
              aria-label={`${f.title} törlése`}
              className="shrink-0 rounded-lg p-1.5 text-mist transition hover:bg-ink-card hover:text-bone disabled:opacity-50"
            >
              {torlesFolyik === kulcs ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
