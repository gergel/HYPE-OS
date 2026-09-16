"use client";

/** ANYAGBEKÉRŐ - publikus beküldői oldal (a felhasználó részletes kérése).
 *
 * Három lépés: 1) adatok + mappás feltöltés, 2) videóigények (kreatív
 * brief), 3) ellenőrzés és véglegesítés. A fájlok KÖZVETLENÜL az R2-be
 * mennek darabolt (multipart) feltöltéssel, rövid élettartamú aláírt
 * URL-ekkel - korlátozott párhuzamossággal, automatikus újrapróbálással,
 * fájlonkénti és összesített folyamatjelzéssel. A brief automatikusan
 * mentődik. A beküldő a saját, titkos folytatási linkjével térhet vissza a
 * piszkozatához - a közös bekérő-link mások leadásaihoz nem ad hozzáférést. */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Logo } from "@/components/Logo";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/api/v1/public/anyagbekeres";

type Bekeres = {
  nev: string;
  udvozlo_szoveg: string | null;
  hatarido: string | null;
  kell_brief: boolean;
  engedett_tipusok: string | null;
  meret_keret_bajt: number | null;
  jelszo_kell: boolean;
  lezart: boolean;
  lejart: boolean;
  fogadokepes: boolean;
};

type MappaT = { id: number; szulo_id: number | null; nev: string; utvonal: string; leiras: string | null };
type FajlT = {
  id: number;
  mappa_id: number | null;
  nev: string;
  relativ_utvonal: string | null;
  meret_bajt: number;
  allapot: "feltoltes_alatt" | "kesz" | "hibas";
  kesz_reszek: number[];
};

type IdokodT = { fajl_id: number | null; szoveg: string };
type IgenyT = {
  kulcs: string;
  nev: string;
  leiras: string;
  hossz: string;
  felulet: string[];
  keparany: string;
  hatarido: string;
  teljes_anyagbol: boolean;
  reszletek: Record<string, string>;
  idokodok: IdokodT[];
  mappa_idk: number[];
  fajl_idk: number[];
  nyitva: boolean;
};

type HelyiFeltoltes = {
  file: File;
  betoltott: number;
  hiba: string | null;
};

const FELULETEK = ["Instagram", "TikTok", "YouTube", "Weboldal", "Rendezvényvetítés", "Egyéb"];
const KEPARANYOK = ["16:9", "9:16", "1:1", "4:5", "Rátok bízom"];
const RESZLET_MEZOK: [string, string][] = [
  ["cel", "Cél és célközönség"],
  ["stilus", "Stílus és hangulat"],
  ["kotelezo", "Kötelezően szereplő jelenetek, személyek, termékek"],
  ["kihagyando", "Kihagyandó részek"],
  ["felirat", "Feliratigény és nyelv"],
  ["szovegek", "Képernyőn megjelenő szövegek és CTA"],
  ["zene", "Zeneigény és narráció"],
  ["referenciak", "Referencialinkek, rövid magyarázattal"],
  ["technikai", "Technikai elvárások"],
  ["egyeb", "Egyéb megjegyzések"],
];

function meretSzoveg(bajt: number): string {
  if (bajt >= 1024 ** 3) return `${(bajt / 1024 ** 3).toFixed(2)} GB`;
  if (bajt >= 1024 ** 2) return `${(bajt / 1024 ** 2).toFixed(1)} MB`;
  if (bajt >= 1024) return `${Math.round(bajt / 1024)} kB`;
  return `${bajt} B`;
}

function idoSzoveg(mp: number): string {
  if (!isFinite(mp) || mp <= 0) return "";
  if (mp < 60) return `~${Math.ceil(mp)} mp`;
  if (mp < 3600) return `~${Math.ceil(mp / 60)} perc`;
  return `~${(mp / 3600).toFixed(1)} óra`;
}

function ujKulcs(): string {
  return Math.random().toString(36).slice(2, 10);
}

/** Egy behúzott/kiválasztott fájl a relatív MAPPA-útvonalával. */
type BejovoFajl = { file: File; mappaUtvonal: string };

/** Drag&drop mappa-bejárás: a DataTransferItem webkitGetAsEntry API-jával a
 * ledobott mappák TELJES tartalmát összegyűjti, az eredeti struktúrával. */
async function dropFajlok(dt: DataTransfer): Promise<BejovoFajl[]> {
  const eredmeny: BejovoFajl[] = [];
  const bejar = async (entry: FileSystemEntry, utvonal: string): Promise<void> => {
    if (entry.isFile) {
      const file = await new Promise<File>((resolve, reject) => (entry as FileSystemFileEntry).file(resolve, reject));
      eredmeny.push({ file, mappaUtvonal: utvonal });
    } else if (entry.isDirectory) {
      const olvaso = (entry as FileSystemDirectoryEntry).createReader();
      // A readEntries adagokban ad vissza - addig kell hívni, míg nem üres.
      let adag: FileSystemEntry[];
      do {
        adag = await new Promise<FileSystemEntry[]>((resolve, reject) => olvaso.readEntries(resolve, reject));
        for (const gyerek of adag) {
          await bejar(gyerek, utvonal ? `${utvonal}/${entry.name}` : entry.name);
        }
      } while (adag.length > 0);
    }
  };
  const entryk = Array.from(dt.items)
    .map((i) => (i.webkitGetAsEntry ? i.webkitGetAsEntry() : null))
    .filter((e): e is FileSystemEntry => e !== null);
  if (entryk.length > 0) {
    for (const e of entryk) await bejar(e, "");
  } else {
    for (const f of Array.from(dt.files)) eredmeny.push({ file: f, mappaUtvonal: "" });
  }
  return eredmeny;
}

export function BekuldoOldal({ bekeresToken }: { bekeresToken: string }) {
  const [bekeres, setBekeres] = useState<Bekeres | null>(null);
  const [betoltesHiba, setBetoltesHiba] = useState<string | null>(null);
  const [leadasToken, setLeadasToken] = useState<string | null>(null);
  const [leadas, setLeadas] = useState<{ id: number; allapot: string; bekuldo_nev: string; bekuldo_email: string; bekuldo_ceg: string | null } | null>(null);
  const [mappak, setMappak] = useState<MappaT[]>([]);
  const [fajlok, setFajlok] = useState<FajlT[]>([]);
  const [igenyek, setIgenyek] = useState<IgenyT[]>([]);
  const [reszMeret, setReszMeret] = useState(100 * 1024 * 1024);
  const [lepes, setLepes] = useState<1 | 2 | 3>(1);
  const [hiba, setHiba] = useState<string | null>(null);
  const [kesz, setKesz] = useState<{ leadasId: number } | null>(null);

  // Nyitó űrlap (új leadás)
  const [nyito, setNyito] = useState({ nev: "", email: "", ceg: "", jelszo: "" });
  const [nyitoBusy, setNyitoBusy] = useState(false);

  // Feltöltés-motor állapota
  const helyiRef = useRef<Map<number, HelyiFeltoltes>>(new Map());
  const [, ujrarajzol] = useState(0);
  const frissit = useCallback(() => ujrarajzol((n) => n + 1), []);
  const sorRef = useRef<number[]>([]);
  const aktivRef = useRef(0);
  const sebessegRef = useRef<{ t: number; b: number }[]>([]);
  const [celMappa, setCelMappa] = useState<number | "">("");

  const tokenRef = useRef<string | null>(null);
  tokenRef.current = leadasToken;

  const taroloKulcs = `anyagbekeres_leadas_${bekeresToken}`;

  // ── Betöltés ──────────────────────────────────────────────────────────────

  useEffect(() => {
    fetch(`${API}/${bekeresToken}`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `Hiba (${r.status})`);
        setBekeres(await r.json());
      })
      .catch((e) => setBetoltesHiba(String(e.message || e)));
    // Folytatás: ?leadas=... az URL-ben, vagy a böngészőben megjegyzett token.
    let t: string | null = null;
    try {
      t = new URLSearchParams(window.location.search).get("leadas") || localStorage.getItem(taroloKulcs);
    } catch {
      /* privát mód */
    }
    if (t) void leadasBetoltese(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bekeresToken]);

  async function leadasBetoltese(t: string) {
    const r = await fetch(`${API}/leadas/${t}`);
    if (!r.ok) {
      try {
        localStorage.removeItem(taroloKulcs);
      } catch {
        /* nem baj */
      }
      return;
    }
    const d = await r.json();
    setLeadasToken(t);
    try {
      localStorage.setItem(taroloKulcs, t);
    } catch {
      /* privát mód */
    }
    alkalmazd(d);
    if (d.leadas.allapot !== "piszkozat") setKesz({ leadasId: d.leadas.id });
  }

  function alkalmazd(d: {
    leadas: { id: number; allapot: string; bekuldo_nev: string; bekuldo_email: string; bekuldo_ceg: string | null };
    mappak: MappaT[];
    fajlok: FajlT[];
    igenyek: (Omit<IgenyT, "kulcs" | "nyitva" | "felulet" | "reszletek" | "hatarido"> & {
      felulet: string | null;
      reszletek: Record<string, string>;
      hatarido: string | null;
    })[];
    resz_meret: number;
  }) {
    setLeadas(d.leadas);
    setMappak(d.mappak);
    setFajlok(d.fajlok);
    setReszMeret(d.resz_meret);
    setIgenyek(
      d.igenyek.map((i) => ({
        kulcs: ujKulcs(),
        nev: i.nev,
        leiras: i.leiras ?? "",
        hossz: i.hossz ?? "",
        felulet: (i.felulet ?? "").split(",").map((s) => s.trim()).filter(Boolean),
        keparany: i.keparany ?? "",
        hatarido: i.hatarido ? i.hatarido.slice(0, 10) : "",
        teljes_anyagbol: i.teljes_anyagbol,
        reszletek: i.reszletek ?? {},
        idokodok: (i.idokodok ?? []) as IdokodT[],
        mappa_idk: i.mappa_idk ?? [],
        fajl_idk: i.fajl_idk ?? [],
        nyitva: false,
      })),
    );
  }

  async function leadasFrissites() {
    const t = tokenRef.current;
    if (!t) return;
    const r = await fetch(`${API}/leadas/${t}`);
    if (r.ok) {
      const d = await r.json();
      setLeadas(d.leadas);
      setMappak(d.mappak);
      setFajlok(d.fajlok);
    }
  }

  // ── Új leadás nyitása ─────────────────────────────────────────────────────

  async function leadasNyitasa() {
    setNyitoBusy(true);
    setHiba(null);
    try {
      const r = await fetch(`${API}/${bekeresToken}/leadas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bekuldo_nev: nyito.nev,
          bekuldo_email: nyito.email,
          bekuldo_ceg: nyito.ceg || null,
          jelszo: nyito.jelszo || null,
        }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        setHiba(d?.detail ?? `Hiba (${r.status})`);
        return;
      }
      await leadasBetoltese(d.leadas_token);
    } catch (e) {
      setHiba(`Hálózati hiba: ${e}`);
    } finally {
      setNyitoBusy(false);
    }
  }

  // ── Feltöltés-motor ───────────────────────────────────────────────────────

  const PARHUZAMOS = 2;

  const toltodik = fajlok.some((f) => f.allapot === "feltoltes_alatt" && helyiRef.current.has(f.id));

  useEffect(() => {
    if (!toltodik) return;
    const figyelmeztet = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", figyelmeztet);
    return () => window.removeEventListener("beforeunload", figyelmeztet);
  }, [toltodik]);

  function sebesseg(): { bps: number; hatraMp: number } {
    const most = Date.now();
    sebessegRef.current = sebessegRef.current.filter((p) => most - p.t < 15000);
    const pontok = sebessegRef.current;
    if (pontok.length < 2) return { bps: 0, hatraMp: Infinity };
    const dt = (pontok[pontok.length - 1].t - pontok[0].t) / 1000;
    const db = pontok[pontok.length - 1].b - pontok[0].b;
    const bps = dt > 0 ? db / dt : 0;
    const hatra = osszesites.teljes - osszesites.betoltott;
    return { bps, hatraMp: bps > 0 ? hatra / bps : Infinity };
  }

  async function reszFeltoltes(url: string, blob: Blob, onProgress: (b: number) => void): Promise<string> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", url);
      xhr.upload.onprogress = (e) => onProgress(e.loaded);
      xhr.onload = () => {
        const etag = xhr.getResponseHeader("ETag");
        if (xhr.status >= 200 && xhr.status < 300 && etag) resolve(etag);
        else reject(new Error(`Darab-feltöltés sikertelen (${xhr.status})`));
      };
      xhr.onerror = () => reject(new Error("Hálózati hiba a darab feltöltésénél"));
      xhr.send(blob);
    });
  }

  async function fajlFuttatasa(fajlId: number) {
    const t = tokenRef.current;
    const helyi = helyiRef.current.get(fajlId);
    if (!t || !helyi) return;
    const fajl = () => helyiRef.current.get(fajlId);
    try {
      const szerverFajl = fajlokRef.current.find((f) => f.id === fajlId);
      const keszek = new Set(szerverFajl?.kesz_reszek ?? []);
      const osszDarab = Math.ceil(helyi.file.size / reszMeret);
      let betoltottAlap = 0;
      for (const p of keszek) betoltottAlap += Math.min(reszMeret, helyi.file.size - (p - 1) * reszMeret);
      helyi.betoltott = betoltottAlap;
      for (let darab = 1; darab <= osszDarab; darab++) {
        if (keszek.has(darab)) continue;
        const blob = helyi.file.slice((darab - 1) * reszMeret, Math.min(darab * reszMeret, helyi.file.size));
        // Automatikus újrapróbálás átmeneti hibánál (3 kísérlet, növekvő várakozással).
        let utolsoHiba: unknown = null;
        for (let kiserlet = 0; kiserlet < 3; kiserlet++) {
          try {
            const sr = await fetch(`${API}/leadas/${t}/fajl/${fajlId}/sign`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ part_number: darab }),
            });
            if (!sr.ok) throw new Error((await sr.json().catch(() => null))?.detail ?? `Aláírás sikertelen (${sr.status})`);
            const { url } = await sr.json();
            const alap = helyi.betoltott;
            const etag = await reszFeltoltes(url, blob, (b) => {
              helyi.betoltott = alap + b;
              sebessegRef.current.push({ t: Date.now(), b: osszBetoltott() });
              frissit();
            });
            helyi.betoltott = alap + blob.size;
            await fetch(`${API}/leadas/${t}/fajl/${fajlId}/resz-kesz`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ part_number: darab, etag: etag.replaceAll('"', "") }),
            });
            utolsoHiba = null;
            break;
          } catch (e) {
            utolsoHiba = e;
            await new Promise((r) => setTimeout(r, 1500 * (kiserlet + 1)));
          }
        }
        if (utolsoHiba) throw utolsoHiba;
      }
      const br = await fetch(`${API}/leadas/${t}/fajl/${fajlId}/befejez`, { method: "POST" });
      if (!br.ok) throw new Error((await br.json().catch(() => null))?.detail ?? "A feltöltés lezárása nem sikerült.");
      helyiRef.current.delete(fajlId);
      setFajlok((elozo) => elozo.map((f) => (f.id === fajlId ? { ...f, allapot: "kesz" } : f)));
    } catch (e) {
      const h = fajl();
      if (h) h.hiba = String((e as Error).message || e);
      setFajlok((elozo) => elozo.map((f) => (f.id === fajlId ? { ...f, allapot: "hibas" } : f)));
    } finally {
      aktivRef.current -= 1;
      frissit();
      inditsd();
    }
  }

  function inditsd() {
    while (aktivRef.current < PARHUZAMOS && sorRef.current.length > 0) {
      const id = sorRef.current.shift()!;
      if (!helyiRef.current.has(id)) continue;
      aktivRef.current += 1;
      void fajlFuttatasa(id);
    }
  }

  const fajlokRef = useRef<FajlT[]>([]);
  fajlokRef.current = fajlok;

  function osszBetoltott(): number {
    let ossz = 0;
    for (const [, h] of helyiRef.current) ossz += h.betoltott;
    return ossz;
  }

  /** Új fájlok felvétele: init a szerveren (típus/kvóta/útvonal-ellenőrzés
   * ott), aztán sorba állítás. Ha egy "hiányzó" (frissítés előtt elkezdett)
   * fájllal egyezik név+méret szerint, azt FOLYTATJA - a kész darabok nem
   * mennek fel újra. */
  async function fajlokFelvetele(bejovok: BejovoFajl[]) {
    const t = tokenRef.current;
    if (!t || bejovok.length === 0) return;
    setHiba(null);
    const hibak: string[] = [];
    for (const be of bejovok) {
      const mappaUtvonal = be.mappaUtvonal;
      // Folytatás: azonos útvonal+név+méret, félbe maradt szerver-sor.
      const meglevo = fajlokRef.current.find(
        (f) =>
          f.allapot === "feltoltes_alatt" &&
          !helyiRef.current.has(f.id) &&
          f.nev === be.file.name &&
          f.meret_bajt === be.file.size &&
          ((f.relativ_utvonal ?? f.nev) === (mappaUtvonal ? `${mappaUtvonal}/${be.file.name}` : be.file.name) ||
            celMappa !== ""),
      );
      if (meglevo) {
        helyiRef.current.set(meglevo.id, { file: be.file, betoltott: 0, hiba: null });
        sorRef.current.push(meglevo.id);
        continue;
      }
      try {
        const r = await fetch(`${API}/leadas/${t}/fajl/init`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            nev: be.file.name,
            relativ_mappa: mappaUtvonal || null,
            mappa_id: mappaUtvonal ? null : celMappa === "" ? null : celMappa,
            meret_bajt: be.file.size,
            content_type: be.file.type || null,
          }),
        });
        const d = await r.json().catch(() => null);
        if (!r.ok) {
          hibak.push(`${be.file.name}: ${d?.detail ?? r.status}`);
          continue;
        }
        helyiRef.current.set(d.fajl_id, { file: be.file, betoltott: 0, hiba: null });
        sorRef.current.push(d.fajl_id);
      } catch (e) {
        hibak.push(`${be.file.name}: ${e}`);
      }
    }
    await leadasFrissites();
    if (hibak.length > 0) setHiba(`Nem minden fájl indult el:\n${hibak.slice(0, 5).join("\n")}${hibak.length > 5 ? `\n… és még ${hibak.length - 5}` : ""}`);
    inditsd();
  }

  async function fajlTorles(fajlId: number) {
    const t = tokenRef.current;
    if (!t) return;
    helyiRef.current.delete(fajlId);
    sorRef.current = sorRef.current.filter((i) => i !== fajlId);
    await fetch(`${API}/leadas/${t}/fajl/${fajlId}`, { method: "DELETE" }).catch(() => null);
    await leadasFrissites();
  }

  async function fajlUjra(f: FajlT) {
    // Hibás fájl újraindítása: a helyi File megvan-e még?
    const helyi = helyiRef.current.get(f.id);
    if (helyi) {
      helyi.hiba = null;
      setFajlok((elozo) => elozo.map((x) => (x.id === f.id ? { ...x, allapot: "feltoltes_alatt" } : x)));
      sorRef.current.push(f.id);
      inditsd();
    }
  }

  const osszesites = useMemo(() => {
    let teljes = 0;
    let betoltott = 0;
    for (const f of fajlok) {
      if (f.allapot === "kesz") {
        teljes += f.meret_bajt;
        betoltott += f.meret_bajt;
      } else if (helyiRef.current.has(f.id)) {
        teljes += f.meret_bajt;
        betoltott += Math.min(helyiRef.current.get(f.id)!.betoltott, f.meret_bajt);
      }
    }
    return { teljes, betoltott };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fajlok, toltodik, helyiRef.current.size, osszBetoltott()]);

  // ── Mappák ────────────────────────────────────────────────────────────────

  const [ujMappaNev, setUjMappaNev] = useState("");

  async function mappaLetrehozas() {
    const t = tokenRef.current;
    if (!t || !ujMappaNev.trim()) return;
    const r = await fetch(`${API}/leadas/${t}/mappa`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nev: ujMappaNev.trim(), szulo_id: celMappa === "" ? null : celMappa }),
    });
    if (r.ok) {
      setUjMappaNev("");
      await leadasFrissites();
    } else {
      setHiba((await r.json().catch(() => null))?.detail ?? "A mappa létrehozása nem sikerült.");
    }
  }

  const mappaLeirasIdozito = useRef<Record<number, ReturnType<typeof setTimeout>>>({});

  function mappaLeiras(mappaId: number, leiras: string) {
    setMappak((elozo) => elozo.map((m) => (m.id === mappaId ? { ...m, leiras } : m)));
    clearTimeout(mappaLeirasIdozito.current[mappaId]);
    mappaLeirasIdozito.current[mappaId] = setTimeout(() => {
      const t = tokenRef.current;
      if (!t) return;
      void fetch(`${API}/leadas/${t}/mappa/${mappaId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ leiras }),
      });
    }, 900);
  }

  async function fajlAthelyezes(fajlId: number, mappaId: number | null) {
    const t = tokenRef.current;
    if (!t) return;
    await fetch(`${API}/leadas/${t}/fajl/${fajlId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mappa_id: mappaId }),
    });
    await leadasFrissites();
  }

  // ── Brief (automatikus mentés) ───────────────────────────────────────────

  const [mentes, setMentes] = useState<"mentve" | "ment" | "hiba" | null>(null);
  const mentesIdozito = useRef<ReturnType<typeof setTimeout> | null>(null);
  const elsoBetoltes = useRef(true);

  useEffect(() => {
    if (!leadasToken || kesz) return;
    if (elsoBetoltes.current) {
      elsoBetoltes.current = false;
      return;
    }
    setMentes("ment");
    if (mentesIdozito.current) clearTimeout(mentesIdozito.current);
    mentesIdozito.current = setTimeout(async () => {
      try {
        const r = await fetch(`${API}/leadas/${leadasToken}/igenyek`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            igenyek: igenyek
              .filter((i) => i.nev.trim())
              .map((i) => ({
                nev: i.nev,
                leiras: i.leiras || null,
                hossz: i.hossz || null,
                felulet: i.felulet.join(", ") || null,
                keparany: i.keparany || null,
                hatarido: i.hatarido || null,
                teljes_anyagbol: i.teljes_anyagbol,
                reszletek: Object.fromEntries(Object.entries(i.reszletek).filter(([, v]) => v?.trim())),
                idokodok: i.idokodok.filter((x) => x.szoveg.trim()),
                mappa_idk: i.mappa_idk,
                fajl_idk: i.fajl_idk,
              })),
          }),
        });
        setMentes(r.ok ? "mentve" : "hiba");
      } catch {
        setMentes("hiba");
      }
    }, 1200);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [igenyek]);

  function igenyModositas(kulcs: string, valtozas: Partial<IgenyT>) {
    setIgenyek((elozo) => elozo.map((i) => (i.kulcs === kulcs ? { ...i, ...valtozas } : i)));
  }

  function ujIgeny() {
    setIgenyek((elozo) => [
      ...elozo.map((i) => ({ ...i, nyitva: false })),
      {
        kulcs: ujKulcs(),
        nev: "",
        leiras: "",
        hossz: "",
        felulet: [],
        keparany: "",
        hatarido: "",
        teljes_anyagbol: false,
        reszletek: {},
        idokodok: [],
        mappa_idk: [],
        fajl_idk: [],
        nyitva: true,
      },
    ]);
  }

  // ── Véglegesítés ──────────────────────────────────────────────────────────

  const [veglegesitBusy, setVeglegesitBusy] = useState(false);

  const fuggoFajlok = fajlok.filter((f) => f.allapot === "feltoltes_alatt");
  const hibasFajlok = fajlok.filter((f) => f.allapot === "hibas");
  const keszFajlok = fajlok.filter((f) => f.allapot === "kesz");
  const veglegesitheto = keszFajlok.length > 0 && fuggoFajlok.length === 0 && hibasFajlok.length === 0 && !veglegesitBusy;

  async function veglegesites() {
    const t = tokenRef.current;
    if (!t || veglegesitBusy) return;
    setVeglegesitBusy(true);
    setHiba(null);
    try {
      // A brief friss állapota menjen fel a véglegesítés ELŐTT.
      if (mentesIdozito.current) clearTimeout(mentesIdozito.current);
      await fetch(`${API}/leadas/${t}/igenyek`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          igenyek: igenyek
            .filter((i) => i.nev.trim())
            .map((i) => ({
              nev: i.nev,
              leiras: i.leiras || null,
              hossz: i.hossz || null,
              felulet: i.felulet.join(", ") || null,
              keparany: i.keparany || null,
              hatarido: i.hatarido || null,
              teljes_anyagbol: i.teljes_anyagbol,
              reszletek: Object.fromEntries(Object.entries(i.reszletek).filter(([, v]) => v?.trim())),
              idokodok: i.idokodok.filter((x) => x.szoveg.trim()),
              mappa_idk: i.mappa_idk,
              fajl_idk: i.fajl_idk,
            })),
        }),
      });
      const r = await fetch(`${API}/leadas/${t}/veglegesit`, { method: "POST" });
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        setHiba(d?.detail ?? `Hiba (${r.status})`);
        return;
      }
      setKesz({ leadasId: d.leadas_id });
    } catch (e) {
      setHiba(`Hálózati hiba: ${e}`);
    } finally {
      setVeglegesitBusy(false);
    }
  }

  // ── Megjelenítés ──────────────────────────────────────────────────────────

  const doboz = "rounded-[var(--radius-lg)] border border-border bg-surface-2 p-5";
  const input = "w-full rounded-[var(--radius)] border border-border bg-surface-1 px-3 py-2 text-[14px] text-text-primary focus:outline-none focus:ring-1 focus:ring-text-accent/40";
  const gombElsodleges = "rounded-[var(--radius)] bg-bg-accent px-4 py-2 text-[14px] font-medium text-text-accent hover:opacity-90 disabled:opacity-40";
  const gombMasodlagos = "rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-40";

  if (betoltesHiba) {
    return (
      <Keret>
        <div className={`${doboz} text-center`}>
          <p className="text-[15px] text-text-primary">Ez a link nem elérhető.</p>
          <p className="mt-1 text-[13px] text-text-muted">{betoltesHiba}</p>
        </div>
      </Keret>
    );
  }
  if (!bekeres) {
    return (
      <Keret>
        <p className="text-center text-[13px] text-text-muted">Betöltés…</p>
      </Keret>
    );
  }

  const hataridoSzoveg = bekeres.hatarido
    ? new Date(bekeres.hatarido + "Z").toLocaleString("hu-HU", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })
    : null;

  const fej = (
    <div className="mb-5 md:mb-6">
      <Logo className="h-6 md:h-7" />
      <h1 className="mt-3 text-[19px] font-semibold text-text-primary md:mt-4 md:text-[22px]">{bekeres.nev}</h1>
      {bekeres.udvozlo_szoveg && <p className="mt-2 max-w-2xl whitespace-pre-line text-[14px] text-text-secondary">{bekeres.udvozlo_szoveg}</p>}
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-text-muted">
        {hataridoSzoveg && <span>Leadási határidő: <b className="text-text-secondary">{hataridoSzoveg}</b></span>}
        {bekeres.engedett_tipusok && <span>Fogadott fájltípusok: {bekeres.engedett_tipusok}</span>}
        {bekeres.meret_keret_bajt && <span>Feltöltési keret: {meretSzoveg(bekeres.meret_keret_bajt)}</span>}
      </div>
    </div>
  );

  // Lezárt/lejárt link, amikor még nincs elkezdett leadás
  if (!leadasToken && !bekeres.fogadokepes) {
    return (
      <Keret>
        {fej}
        <div className={`${doboz} text-center`}>
          <p className="text-[15px] text-text-primary">
            {bekeres.lezart ? "Ez az anyagbekérés lezárult." : "Ez a link lejárt."}
          </p>
          <p className="mt-1 text-[13px] text-text-muted">Ha még anyagot kell leadnod, kérj új linket a HYPE kapcsolattartódtól.</p>
        </div>
      </Keret>
    );
  }

  // Sikeres leadás után
  if (kesz && leadas) {
    return (
      <Keret>
        {fej}
        <div className={doboz}>
          <p className="text-[17px] font-semibold text-text-primary">Az anyagokat megkaptuk.</p>
          <p className="mt-1 text-[13px] text-text-muted">Leadás azonosítója: <b className="text-text-secondary">#{kesz.leadasId}</b></p>
          <div className="mt-4 grid gap-2 text-[13.5px] text-text-secondary">
            <p><b className="text-text-primary">{leadas.bekuldo_nev}</b>{leadas.bekuldo_ceg ? ` · ${leadas.bekuldo_ceg}` : ""} · {leadas.bekuldo_email}</p>
            <p>{keszFajlok.length} fájl · {mappak.length} mappa · {meretSzoveg(keszFajlok.reduce((s, f) => s + f.meret_bajt, 0))}</p>
            {bekeres.kell_brief && <p>{igenyek.filter((i) => i.nev.trim()).length} kért videó</p>}
          </div>
          <p className="mt-4 text-[12.5px] text-text-muted">Köszönjük! A csapatunk hamarosan feldolgozza a leadást, és jelentkezünk, ha bármi kérdés van.</p>
        </div>
      </Keret>
    );
  }

  // Nyitó űrlap (még nincs saját leadás)
  if (!leadasToken || !leadas) {
    return (
      <Keret>
        {fej}
        <div className={`${doboz} max-w-xl`}>
          <p className="mb-3 text-[15px] font-medium text-text-primary">Kezdjük az adataiddal</p>
          <div className="grid gap-3">
            <label className="text-[12.5px] text-text-muted">Név *
              <input className={input} value={nyito.nev} onChange={(e) => setNyito({ ...nyito, nev: e.target.value })} autoComplete="name" />
            </label>
            <label className="text-[12.5px] text-text-muted">E-mail cím *
              <input className={input} type="email" value={nyito.email} onChange={(e) => setNyito({ ...nyito, email: e.target.value })} autoComplete="email" />
            </label>
            <label className="text-[12.5px] text-text-muted">Cég (nem kötelező)
              <input className={input} value={nyito.ceg} onChange={(e) => setNyito({ ...nyito, ceg: e.target.value })} autoComplete="organization" />
            </label>
            {bekeres.jelszo_kell && (
              <label className="text-[12.5px] text-text-muted">A linkhez kapott jelszó *
                <input className={input} type="password" value={nyito.jelszo} onChange={(e) => setNyito({ ...nyito, jelszo: e.target.value })} />
              </label>
            )}
          </div>
          {hiba && <p className="mt-3 whitespace-pre-line text-[13px] text-text-danger">{hiba}</p>}
          <button
            type="button"
            disabled={nyitoBusy || !nyito.nev.trim() || !nyito.email.includes("@") || (bekeres.jelszo_kell && !nyito.jelszo)}
            onClick={() => void leadasNyitasa()}
            className={`${gombElsodleges} mt-4`}
          >
            {nyitoBusy ? "Indítás…" : "Feltöltés megkezdése"}
          </button>
          <p className="mt-3 text-[12px] text-text-muted">
            Az indítás után kapsz egy saját folytatási linket - azzal bármikor visszatérhetsz a piszkozatodhoz.
          </p>
        </div>
      </Keret>
    );
  }

  const folytatasiLink = typeof window !== "undefined" ? `${window.location.origin}/anyagbekeres/${bekeresToken}?leadas=${leadasToken}` : "";
  const seb = sebesseg();
  const gyoker = mappak.filter((m) => m.szulo_id === null);

  const lepesGomb = (n: 1 | 2 | 3, cim: string) => (
    <button
      type="button"
      onClick={() => setLepes(n)}
      className={`shrink-0 rounded-[var(--radius)] px-2.5 py-1.5 text-[12.5px] md:px-3 md:text-[13px] ${lepes === n ? "bg-bg-accent font-medium text-text-accent" : "text-text-secondary hover:bg-surface-3"}`}
    >
      {n}. {cim}
    </button>
  );

  return (
    <Keret szeles>
      {fej}
      {/* Mentési és feltöltési állapot mindig látható sávban - telefonon a
          lépések vízszintesen görgethetők, semmi nem törik több sorba. */}
      <div className="mb-4 flex flex-col gap-1.5 text-[12.5px] md:flex-row md:flex-wrap md:items-center md:gap-x-4">
        <div className="-mx-1 flex gap-1 overflow-x-auto px-1">{lepesGomb(1, "Feltöltés")}{bekeres.kell_brief && lepesGomb(2, "Milyen videók?")}{lepesGomb(3, "Leadás")}</div>
        <span className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-text-muted md:ml-auto">
          {toltodik && (
            <span className="text-text-secondary">
              Feltöltés: {meretSzoveg(osszesites.betoltott)} / {meretSzoveg(osszesites.teljes)}
              {seb.bps > 0 && <> · {meretSzoveg(seb.bps)}/mp · {idoSzoveg(seb.hatraMp)} van hátra</>}
            </span>
          )}
          {mentes === "ment" && <span>Mentés…</span>}
          {mentes === "mentve" && <span>Minden változás mentve</span>}
          {mentes === "hiba" && <span className="text-text-danger">A mentés nem sikerült - újrapróbáljuk</span>}
        </span>
      </div>
      {hiba && <p className="mb-3 whitespace-pre-line rounded-[var(--radius)] border border-text-danger/40 bg-bg-danger/30 px-3 py-2 text-[13px] text-text-danger">{hiba}</p>}

      {lepes === 1 && (
        <ElsoLepes
          doboz={doboz}
          input={input}
          gombMasodlagos={gombMasodlagos}
          bekeres={bekeres}
          mappak={mappak}
          gyoker={gyoker}
          fajlok={fajlok}
          helyi={helyiRef.current}
          celMappa={celMappa}
          setCelMappa={setCelMappa}
          ujMappaNev={ujMappaNev}
          setUjMappaNev={setUjMappaNev}
          mappaLetrehozas={mappaLetrehozas}
          mappaLeiras={mappaLeiras}
          fajlokFelvetele={fajlokFelvetele}
          fajlTorles={fajlTorles}
          fajlUjra={fajlUjra}
          fajlAthelyezes={fajlAthelyezes}
          folytatasiLink={folytatasiLink}
          tovabb={() => setLepes(bekeres.kell_brief ? 2 : 3)}
        />
      )}

      {lepes === 2 && bekeres.kell_brief && (
        <MasodikLepes
          doboz={doboz}
          input={input}
          gombMasodlagos={gombMasodlagos}
          gombElsodleges={gombElsodleges}
          igenyek={igenyek}
          setIgenyek={setIgenyek}
          igenyModositas={igenyModositas}
          ujIgeny={ujIgeny}
          mappak={mappak}
          fajlok={fajlok}
          tovabb={() => setLepes(3)}
        />
      )}

      {lepes === 3 && (
        <div className="grid gap-4">
          <div className={doboz}>
            <p className="mb-3 text-[15px] font-medium text-text-primary">Összefoglaló</p>
            <div className="grid gap-1.5 text-[13.5px] text-text-secondary">
              <p><b className="text-text-primary">{leadas.bekuldo_nev}</b>{leadas.bekuldo_ceg ? ` · ${leadas.bekuldo_ceg}` : ""} · {leadas.bekuldo_email}</p>
              <p>{mappak.length} mappa · {keszFajlok.length} kész fájl · {meretSzoveg(keszFajlok.reduce((s, f) => s + f.meret_bajt, 0))}</p>
              {fuggoFajlok.length > 0 && <p className="text-text-warning">{fuggoFajlok.length} fájl feltöltése még folyamatban vagy megszakadt.</p>}
              {hibasFajlok.length > 0 && <p className="text-text-danger">{hibasFajlok.length} hibás fájl - próbáld újra vagy távolítsd el az 1. lépésben.</p>}
              {bekeres.kell_brief && (
                <>
                  <p className="mt-2 font-medium text-text-primary">Kért videók ({igenyek.filter((i) => i.nev.trim()).length})</p>
                  {igenyek.filter((i) => i.nev.trim()).map((i) => (
                    <p key={i.kulcs} className="pl-3">
                      • <b>{i.nev}</b>
                      {i.keparany ? ` · ${i.keparany}` : ""}
                      {i.hossz ? ` · ${i.hossz}` : ""} —{" "}
                      {i.teljes_anyagbol
                        ? "a teljes leadott anyagból"
                        : `${i.mappa_idk.length} mappa + ${i.fajl_idk.length} fájl`}
                    </p>
                  ))}
                  {igenyek.filter((i) => i.nev.trim()).length === 0 && (
                    <p className="text-text-muted">Nincs videóigény megadva - csak fájlleadás.</p>
                  )}
                </>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button type="button" disabled={!veglegesitheto} onClick={() => void veglegesites()} className={gombElsodleges}>
              {veglegesitBusy ? "Leadás…" : "Leadás véglegesítése"}
            </button>
            {!veglegesitheto && keszFajlok.length === 0 && <span className="text-[13px] text-text-muted">Legalább egy sikeresen feltöltött fájl kell a leadáshoz.</span>}
            {!veglegesitheto && (fuggoFajlok.length > 0 || hibasFajlok.length > 0) && (
              <span className="text-[13px] text-text-muted">A véglegesítéshez minden megtartott fájlnak sikeresen fel kell töltődnie.</span>
            )}
          </div>
        </div>
      )}
    </Keret>
  );
}

function Keret({ children, szeles = false }: { children: React.ReactNode; szeles?: boolean }) {
  return (
    <div className="min-h-screen bg-surface-1 px-4 py-8 text-text-primary md:px-10">
      <div className={szeles ? "mx-auto max-w-5xl" : "mx-auto max-w-2xl"}>{children}</div>
    </div>
  );
}

// ── 1. lépés: feltöltés ──────────────────────────────────────────────────────

function ElsoLepes(props: {
  doboz: string;
  input: string;
  gombMasodlagos: string;
  bekeres: Bekeres;
  mappak: MappaT[];
  gyoker: MappaT[];
  fajlok: FajlT[];
  helyi: Map<number, HelyiFeltoltes>;
  celMappa: number | "";
  setCelMappa: (v: number | "") => void;
  ujMappaNev: string;
  setUjMappaNev: (v: string) => void;
  mappaLetrehozas: () => Promise<void>;
  mappaLeiras: (id: number, leiras: string) => void;
  fajlokFelvetele: (b: BejovoFajl[]) => Promise<void>;
  fajlTorles: (id: number) => Promise<void>;
  fajlUjra: (f: FajlT) => Promise<void>;
  fajlAthelyezes: (id: number, mappaId: number | null) => Promise<void>;
  folytatasiLink: string;
  tovabb: () => void;
}) {
  const { doboz, input, gombMasodlagos, mappak, fajlok, helyi } = props;
  const fajlInput = useRef<HTMLInputElement>(null);
  const mappaInput = useRef<HTMLInputElement>(null);
  const [huzas, setHuzas] = useState(false);
  const [masolva, setMasolva] = useState(false);
  // Mobilon a mappa-feltöltést nem minden böngésző tudja - ott tájékoztatunk.
  const mappaTamogatott = useMemo(() => {
    if (typeof document === "undefined") return true;
    const i = document.createElement("input");
    return "webkitdirectory" in i;
  }, []);

  function kivalasztott(files: FileList | null, mappas: boolean) {
    if (!files) return;
    const bejovok: BejovoFajl[] = Array.from(files).map((f) => {
      const rel = (f as File & { webkitRelativePath?: string }).webkitRelativePath || "";
      const mappa = mappas && rel.includes("/") ? rel.split("/").slice(0, -1).join("/") : "";
      return { file: f, mappaUtvonal: mappa };
    });
    void props.fajlokFelvetele(bejovok);
  }

  const fajlNev = (f: FajlT) => f.relativ_utvonal || f.nev;

  return (
    <div className="grid gap-3 md:gap-4">
      {/* FELTÖLTÉS - telefonon egyetlen nagy gomb a főszereplő, a húzós
          terület és a mappa-feltöltés csak asztali gépen jelenik meg. */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setHuzas(true);
        }}
        onDragLeave={() => setHuzas(false)}
        onDrop={async (e) => {
          e.preventDefault();
          setHuzas(false);
          void props.fajlokFelvetele(await dropFajlok(e.dataTransfer));
        }}
        className={`rounded-[var(--radius-lg)] border-2 border-dashed p-4 transition-colors md:p-8 md:text-center ${huzas ? "border-text-accent bg-bg-accent/20" : "border-border bg-surface-2"}`}
      >
        <p className="hidden text-[15px] font-medium text-text-primary md:block">Húzd ide a fájlokat vagy mappákat</p>
        <p className="hidden text-[13px] text-text-muted md:mt-1 md:block">A mappák és almappák eredeti szerkezete megmarad.</p>
        <div className="flex flex-col gap-2 md:mt-4 md:flex-row md:items-center md:justify-center">
          <button
            type="button"
            onClick={() => fajlInput.current?.click()}
            className="w-full rounded-[var(--radius)] bg-bg-accent px-4 py-3 text-[15px] font-medium text-text-accent hover:opacity-90 md:w-auto md:py-2 md:text-[14px]"
          >
            Fájlok kiválasztása
          </button>
          {mappaTamogatott && (
            <button type="button" onClick={() => mappaInput.current?.click()} className={`hidden md:inline-block ${gombMasodlagos}`}>
              Mappa feltöltése
            </button>
          )}
        </div>
        {/* Cél mappa - közvetlenül a gomb alatt, hogy telefonon egy mozdulat legyen. */}
        {mappak.length > 0 && (
          <label className="mt-3 block text-left text-[12.5px] text-text-muted md:mx-auto md:max-w-sm">
            Hova kerüljenek a fájlok?
            <select
              className={`${input} mt-1`}
              value={props.celMappa}
              onChange={(e) => props.setCelMappa(e.target.value === "" ? "" : Number(e.target.value))}
            >
              <option value="">Mappa nélkül</option>
              {mappak.map((m) => (
                <option key={m.id} value={m.id}>{m.utvonal}</option>
              ))}
            </select>
          </label>
        )}
        <input ref={fajlInput} type="file" multiple className="hidden" onChange={(e) => { kivalasztott(e.target.files, false); e.target.value = ""; }} />
        {/* @ts-expect-error - a webkitdirectory nem szabványos, de minden asztali böngésző ismeri */}
        <input ref={mappaInput} type="file" multiple webkitdirectory="" className="hidden" onChange={(e) => { kivalasztott(e.target.files, true); e.target.value = ""; }} />
      </div>

      {/* Mappák leírással + új mappa - egy kártyában, kevesebb szöveggel. */}
      <div className={doboz}>
        <p className="mb-2 text-[14px] font-medium text-text-primary">Mappák{mappak.length > 0 ? ` (${mappak.length})` : ""}</p>
        {mappak.length > 0 && (
          <div className="mb-3 grid gap-2">
            {mappak.map((m) => {
              const db = fajlok.filter((f) => f.mappa_id === m.id).length;
              return (
                <div key={m.id} className="rounded-[var(--radius)] border border-border bg-surface-1 px-3 py-2">
                  <div className="flex items-center gap-2 text-[13.5px]">
                    <span className="min-w-0 flex-1 truncate font-medium text-text-primary">{m.utvonal}</span>
                    <span className="shrink-0 text-text-muted">{db} fájl</span>
                  </div>
                  <input
                    className="mt-1 w-full bg-transparent text-[13px] text-text-secondary placeholder:text-text-muted focus:outline-none"
                    placeholder="Rövid leírás (nem kötelező)"
                    value={m.leiras ?? ""}
                    onChange={(e) => props.mappaLeiras(m.id, e.target.value)}
                  />
                </div>
              );
            })}
          </div>
        )}
        <div className="flex gap-2">
          <input
            className={`${input} min-w-0 flex-1 md:max-w-xs`}
            placeholder='Új mappa neve (pl. "Interjúk")'
            value={props.ujMappaNev}
            onChange={(e) => props.setUjMappaNev(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void props.mappaLetrehozas()}
          />
          <button type="button" onClick={() => void props.mappaLetrehozas()} disabled={!props.ujMappaNev.trim()} className={`shrink-0 ${gombMasodlagos}`}>
            + Mappa
          </button>
        </div>
      </div>

      {/* Fájllista */}
      {fajlok.length > 0 && (
        <div className={doboz}>
          <p className="mb-2 text-[14px] font-medium text-text-primary">Fájlok ({fajlok.length})</p>
          <div className="grid gap-1.5">
            {fajlok.map((f) => {
              const h = helyi.get(f.id);
              const szazalek = f.allapot === "kesz" ? 100 : h ? Math.min(99, Math.round(((h.betoltott || 0) / Math.max(f.meret_bajt, 1)) * 100)) : 0;
              return (
                <div key={f.id} className="rounded-[var(--radius)] border border-border bg-surface-1 px-3 py-2">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px]">
                    <span className="min-w-0 flex-1 truncate text-text-primary" title={fajlNev(f)}>{fajlNev(f)}</span>
                    <span className="text-text-muted">{meretSzoveg(f.meret_bajt)}</span>
                    {f.allapot === "kesz" && <span className="text-text-success">✓ feltöltve</span>}
                    {f.allapot === "hibas" && <span className="text-text-danger">hiba{h?.hiba ? `: ${h.hiba}` : ""}</span>}
                    {f.allapot === "feltoltes_alatt" && h && <span className="text-text-secondary">{szazalek}%</span>}
                    {f.allapot === "feltoltes_alatt" && !h && (
                      <span className="text-text-warning" title="Oldalfrissítés után a böngészőnek újra ki kell választania a fájlt - a már feltöltött részek nem vesznek el.">
                        félbe maradt - válaszd ki újra a fájlt a folytatáshoz
                      </span>
                    )}
                    <select
                      value={f.mappa_id ?? ""}
                      onChange={(e) => void props.fajlAthelyezes(f.id, e.target.value === "" ? null : Number(e.target.value))}
                      className="rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[12px] text-text-secondary"
                      title="Fájl áthelyezése mappába"
                    >
                      <option value="">(gyökér)</option>
                      {mappak.map((m) => (
                        <option key={m.id} value={m.id}>{m.utvonal}</option>
                      ))}
                    </select>
                    {f.allapot === "hibas" && h && (
                      <button type="button" onClick={() => void props.fajlUjra(f)} className="text-[12.5px] text-text-accent hover:underline">Újra</button>
                    )}
                    <button type="button" onClick={() => void props.fajlTorles(f.id)} className="text-[12.5px] text-text-muted hover:text-text-danger">Eltávolítás</button>
                  </div>
                  {f.allapot === "feltoltes_alatt" && h && (
                    <div className="mt-1.5 h-1 overflow-hidden rounded bg-surface-3">
                      <div className="h-full bg-text-accent transition-[width]" style={{ width: `${szazalek}%` }} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Folytatási link */}
      <div className="flex flex-wrap items-center gap-3 text-[12.5px] text-text-muted">
        <span>Saját folytatási linked (őrizd meg, ezzel térhetsz vissza a piszkozathoz):</span>
        <button
          type="button"
          className={gombMasodlagos}
          onClick={() => {
            void navigator.clipboard?.writeText(props.folytatasiLink).then(() => {
              setMasolva(true);
              setTimeout(() => setMasolva(false), 2000);
            });
          }}
        >
          {masolva ? "Kimásolva ✓" : "Link másolása"}
        </button>
        <button type="button" onClick={props.tovabb} className="ml-auto rounded-[var(--radius)] bg-bg-accent px-4 py-2 text-[14px] font-medium text-text-accent hover:opacity-90">
          Tovább →
        </button>
      </div>
    </div>
  );
}

// ── 2. lépés: videóigények ───────────────────────────────────────────────────

function MasodikLepes(props: {
  doboz: string;
  input: string;
  gombMasodlagos: string;
  gombElsodleges: string;
  igenyek: IgenyT[];
  setIgenyek: React.Dispatch<React.SetStateAction<IgenyT[]>>;
  igenyModositas: (kulcs: string, v: Partial<IgenyT>) => void;
  ujIgeny: () => void;
  mappak: MappaT[];
  fajlok: FajlT[];
  tovabb: () => void;
}) {
  const { doboz, input, gombMasodlagos, igenyek, igenyModositas, mappak, fajlok } = props;

  return (
    <div className="grid gap-4">
      {igenyek.length === 0 && (
        <div className={`${doboz} text-center`}>
          <p className="text-[14px] text-text-secondary">Még nincs videóigény. Írd le, milyen videók készüljenek a feltöltött anyagból.</p>
        </div>
      )}
      {igenyek.map((i, idx) => (
        <div key={i.kulcs} className={doboz}>
          <div className="flex items-center gap-2">
            <button type="button" onClick={() => igenyModositas(i.kulcs, { nyitva: !i.nyitva })} className="text-[13px] text-text-muted">
              {i.nyitva ? "▾" : "▸"}
            </button>
            <input
              className="min-w-0 flex-1 bg-transparent text-[15px] font-medium text-text-primary placeholder:text-text-muted focus:outline-none"
              placeholder={`Videó neve (pl. "Összefoglaló 60 mp")`}
              value={i.nev}
              onChange={(e) => igenyModositas(i.kulcs, { nev: e.target.value })}
            />
            <button
              type="button"
              className={gombMasodlagos}
              title="Videóigény duplikálása"
              onClick={() =>
                props.setIgenyek((elozo) => {
                  const masolat: IgenyT = { ...i, kulcs: ujKulcs(), nev: `${i.nev} (másolat)`, nyitva: true };
                  const uj = [...elozo.map((x) => ({ ...x, nyitva: false }))];
                  uj.splice(idx + 1, 0, masolat);
                  return uj;
                })
              }
            >
              Duplikálás
            </button>
            <button type="button" onClick={() => props.setIgenyek((elozo) => elozo.filter((x) => x.kulcs !== i.kulcs))} className="text-[13px] text-text-muted hover:text-text-danger">
              Törlés
            </button>
          </div>

          {i.nyitva && (
            <div className="mt-4 grid gap-4">
              <label className="text-[12.5px] text-text-muted">Mit szeretnél ebből az anyagból?
                <textarea className={`${input} mt-0.5`} rows={3} value={i.leiras} onChange={(e) => igenyModositas(i.kulcs, { leiras: e.target.value })} />
              </label>

              {/* Forrás-hozzárendelés */}
              <div>
                <p className="mb-1 text-[12.5px] text-text-muted">Miből dolgozzunk?</p>
                <label className="flex items-center gap-2 text-[13.5px] text-text-primary">
                  <input type="checkbox" checked={i.teljes_anyagbol} onChange={(e) => igenyModositas(i.kulcs, { teljes_anyagbol: e.target.checked })} />
                  A teljes leadott anyagból
                </label>
                {!i.teljes_anyagbol && (
                  <div className="mt-2 grid gap-1.5 rounded-[var(--radius)] border border-border bg-surface-1 p-3 md:grid-cols-2">
                    <div>
                      <p className="mb-1 text-[12px] font-medium text-text-secondary">Mappák</p>
                      {mappak.length === 0 && <p className="text-[12px] text-text-muted">Nincs mappa.</p>}
                      {mappak.map((m) => (
                        <label key={m.id} className="flex items-center gap-2 text-[13px] text-text-primary">
                          <input
                            type="checkbox"
                            checked={i.mappa_idk.includes(m.id)}
                            onChange={(e) =>
                              igenyModositas(i.kulcs, {
                                mappa_idk: e.target.checked ? [...i.mappa_idk, m.id] : i.mappa_idk.filter((x) => x !== m.id),
                              })
                            }
                          />
                          {m.utvonal}
                        </label>
                      ))}
                    </div>
                    <div>
                      <p className="mb-1 text-[12px] font-medium text-text-secondary">Egyedi fájlok</p>
                      <div className="max-h-40 overflow-y-auto pr-1">
                        {fajlok.map((f) => (
                          <label key={f.id} className="flex items-center gap-2 text-[13px] text-text-primary">
                            <input
                              type="checkbox"
                              checked={i.fajl_idk.includes(f.id)}
                              onChange={(e) =>
                                igenyModositas(i.kulcs, {
                                  fajl_idk: e.target.checked ? [...i.fajl_idk, f.id] : i.fajl_idk.filter((x) => x !== f.id),
                                })
                              }
                            />
                            <span className="truncate">{f.relativ_utvonal || f.nev}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
                <label className="text-[12.5px] text-text-muted">Tervezett hossz
                  <input className={`${input} mt-0.5`} placeholder="pl. 60-90 mp" value={i.hossz} onChange={(e) => igenyModositas(i.kulcs, { hossz: e.target.value })} />
                </label>
                <label className="text-[12.5px] text-text-muted">Képarány
                  <select className={`${input} mt-0.5`} value={i.keparany} onChange={(e) => igenyModositas(i.kulcs, { keparany: e.target.value })}>
                    <option value="">– válassz –</option>
                    {KEPARANYOK.map((k) => (
                      <option key={k} value={k}>{k}</option>
                    ))}
                  </select>
                </label>
                <label className="text-[12.5px] text-text-muted">Kért elkészülési határidő
                  <input type="date" className={`${input} mt-0.5`} value={i.hatarido} onChange={(e) => igenyModositas(i.kulcs, { hatarido: e.target.value })} />
                </label>
                <div className="text-[12.5px] text-text-muted">Felhasználási felület
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
                    {FELULETEK.map((f) => (
                      <label key={f} className="flex items-center gap-1.5 text-[13px] text-text-primary">
                        <input
                          type="checkbox"
                          checked={i.felulet.includes(f)}
                          onChange={(e) =>
                            igenyModositas(i.kulcs, { felulet: e.target.checked ? [...i.felulet, f] : i.felulet.filter((x) => x !== f) })
                          }
                        />
                        {f}
                      </label>
                    ))}
                  </div>
                </div>
              </div>

              {/* Időkódos megjegyzések */}
              <div>
                <p className="mb-1 text-[12.5px] text-text-muted">Időkódos megjegyzések konkrét fájlokhoz (nem kötelező)</p>
                {i.idokodok.map((x, xi) => (
                  <div key={xi} className="mb-1.5 flex gap-2">
                    <select
                      className={`${input} w-56`}
                      value={x.fajl_id ?? ""}
                      onChange={(e) => {
                        const uj = [...i.idokodok];
                        uj[xi] = { ...x, fajl_id: e.target.value === "" ? null : Number(e.target.value) };
                        igenyModositas(i.kulcs, { idokodok: uj });
                      }}
                    >
                      <option value="">(fájl nélkül)</option>
                      {fajlok.map((f) => (
                        <option key={f.id} value={f.id}>{f.relativ_utvonal || f.nev}</option>
                      ))}
                    </select>
                    <input
                      className={input}
                      placeholder="00:01:12–00:01:45: ez a válasz mindenképp kerüljön bele"
                      value={x.szoveg}
                      onChange={(e) => {
                        const uj = [...i.idokodok];
                        uj[xi] = { ...x, szoveg: e.target.value };
                        igenyModositas(i.kulcs, { idokodok: uj });
                      }}
                    />
                    <button type="button" className="text-[12.5px] text-text-muted hover:text-text-danger" onClick={() => igenyModositas(i.kulcs, { idokodok: i.idokodok.filter((_, j) => j !== xi) })}>
                      ×
                    </button>
                  </div>
                ))}
                <button type="button" className={gombMasodlagos} onClick={() => igenyModositas(i.kulcs, { idokodok: [...i.idokodok, { fajl_id: null, szoveg: "" }] })}>
                  + Időkódos megjegyzés
                </button>
              </div>

              {/* További részletek */}
              <details>
                <summary className="cursor-pointer text-[13px] text-text-accent">További részletek (cél, stílus, feliratok, zene, referenciák…)</summary>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {RESZLET_MEZOK.map(([kulcs, cimke]) => (
                    <label key={kulcs} className="text-[12.5px] text-text-muted">{cimke}
                      <textarea
                        className={`${input} mt-0.5`}
                        rows={2}
                        value={i.reszletek[kulcs] ?? ""}
                        onChange={(e) => igenyModositas(i.kulcs, { reszletek: { ...i.reszletek, [kulcs]: e.target.value } })}
                      />
                    </label>
                  ))}
                </div>
              </details>
            </div>
          )}
        </div>
      ))}

      <div className="flex items-center gap-3">
        <button type="button" onClick={props.ujIgeny} className={gombMasodlagos}>
          + Új videóigény hozzáadása
        </button>
        <button type="button" onClick={props.tovabb} className="ml-auto rounded-[var(--radius)] bg-bg-accent px-4 py-2 text-[14px] font-medium text-text-accent hover:opacity-90">
          Tovább az ellenőrzéshez →
        </button>
      </div>
    </div>
  );
}
