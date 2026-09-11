"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CalendarDays,
  Eye,
  EyeOff,
  Maximize2,
  Minimize2,
  Redo2,
  Search,
  Undo2,
} from "lucide-react";
import { authFetch } from "@/lib/authFetch";
// CSAK TÍPUS a lib/api-ból: az érték szerinti import behúzná a `next/headers`-t
// (a modul szerver oldalon süti-alapú hitelesítéssel hív), ami
// klienskomponensben build-hibát okoz. A színek ezért a kliens-biztos
// lib/diszpoSzin-ből jönnek - ugyanaz a szétválasztás, mint a lib/utokovetes-nél.
import type { DiszpoMunkalap, DiszpoNezet } from "@/lib/api";
import { DISZPO_SZINEK, SZIN_LEIRAS, type DiszpoSzin } from "@/lib/diszpoSzin";
import { DiszpoOszlopValaszto, type OszlopTetel } from "@/components/DiszpoOszlopValaszto";
import { KeresosSelect } from "@/components/KeresosSelect";

// A rács MÉRETEI. Fixek, mert a virtualizálás ebből számol: enélkül minden
// görgetésnél meg kellene mérni a tényleges cellamagasságokat.
const SOR_MAGASSAG = 26;
//: A HÓNAP-ELVÁLASZTÓ sor magasabb és középre írt: az évet egyben görgetve
//: ez az egyetlen fogódzó, hol tart az ember. A Sheetben is kiugrik.
const ELVALASZTO_MAGASSAG = 46;
const OSZLOP_SZELES = 116;
//: Kézi átméretezés határai - ugyanezt tartja a szerver is (lásd backend
//: routes/diszpo_tabla.set_nezet).
const OSZLOP_MIN = 40;
const OSZLOP_MAX = 600;
const SORFEJ_SZELES = 46;
const OSZLOPFEJ_MAGAS = 24;
//: Ennyi sorral/oszloppal többet rajzolunk a látható ablakon kívül, hogy
//: görgetéskor ne villanjon be üres terület.
const RATARTAS = 6;
//: Ennyi lépés fér a visszavonás-naplóba - egy tömeges beillesztés is EGY
//: lépés, tehát ez bőven elég egy napi munkára.
const UNDO_MERET = 200;

/** Oszlopbetű, mint a táblázatban: 0 -> A, 25 -> Z, 26 -> AA. */
function oszlopBetu(idx: number): string {
  let n = idx;
  let s = "";
  do {
    s = String.fromCharCode(65 + (n % 26)) + s;
    n = Math.floor(n / 26) - 1;
  } while (n >= 0);
  return s;
}

/** Cellacím ("B12") felbontása sor/oszlop indexre - a cellacím-mezőhöz. */
function cimbolPont(cim: string): { sor: number; oszlop: number } | null {
  const t = /^([a-zA-Z]+)([0-9]+)$/.exec(cim.trim());
  if (!t) return null;
  let oszlop = 0;
  for (const ch of t[1].toUpperCase()) oszlop = oszlop * 26 + (ch.charCodeAt(0) - 64);
  return { sor: Number(t[2]) - 1, oszlop: oszlop - 1 };
}

/** Ékezet- és kisbetű-független kulcs a táblán belüli kereséshez. */
function keresoKulcs(szoveg: string): string {
  return szoveg
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

type Pont = { sor: number; oszlop: number };
type Tartomany = { tol: Pont; ig: Pont };
type CellaAdat = { ertek: string | null; szin: string | null };

/** Egy cella-módosítás - ugyanaz az alak, amit a szerver PUT /cellak vár,
 * ezért a visszavonás-napló és a mentési sor is ezt hordozza. */
type CellaValt = {
  sor_idx: number;
  oszlop_idx: number;
  ertek?: string | null;
  ertek_valtozik?: boolean;
  szin?: string | null;
  szin_valtozik?: boolean;
};

function normalizal(t: Tartomany) {
  return {
    sor1: Math.min(t.tol.sor, t.ig.sor),
    sor2: Math.max(t.tol.sor, t.ig.sor),
    oszlop1: Math.min(t.tol.oszlop, t.ig.oszlop),
    oszlop2: Math.max(t.tol.oszlop, t.ig.oszlop),
  };
}

function kulcs(sor: number, oszlop: number): number {
  return sor * 10000 + oszlop;
}

/** A HYPE 2026 táblázat egy munkalapja - TÁBLÁZATKÉNT, nem listaként.
 *
 * Úgy kell viselkednie, mint a Google Sheets, mert a munka is ugyanaz: sorok
 * és oszlopok, kijelölés, gépelés, színezés. Ezért van benne sorszám és
 * oszlopbetű, fagyasztott fejléc, billentyűs mozgás, tartomány-kijelölés,
 * sor/oszlop beszúrás, cellacím-mező és szerkesztősáv.
 *
 * A CELLA SZÍNE ITT ADAT: abból számoljuk, ki hány napot dolgozott (lásd
 * backend services/munkanap_szamlalo.py).
 *
 * A SZERKESZTÉS HELYBEN, AZONNAL érvényesül (optimista állapot), a mentés a
 * háttérben, kötegelve megy - az állapotát a "Mentve / Mentés… / Sikertelen"
 * jelző mutatja. Sikertelen mentésnél a beírt tartalom megmarad, és újra
 * lehet próbálni. A visszavonás (Ctrl+Z) a SAJÁT lépéseinket fordítja vissza.
 *
 * MIÉRT VIRTUALIZÁLT? Mert az egész év egyben látszik (a külsős munkalap 381
 * sor x 146 oszlop = 55 ezer cella), és ennyi DOM-elemtől a böngésző megáll.
 * Csak a látható ablakot rajzoljuk ki; a görgetősáv a teljes méretet mutatja,
 * tehát a görgetés ugyanaz, mintha minden ott volna. */
export function DiszpoTablaRacs({
  munkalap,
  canEdit = true,
  canDelete = false,
  canEmberKotes = false,
  rejtettetLatja = false,
  emberek,
  kezdoNezet,
}: {
  munkalap: DiszpoMunkalap;
  canEdit?: boolean;
  canDelete?: boolean;
  /** Az oszlop-ember kötés vezérlője CSAK az adminnak látszik (a felhasználó
   * kérése) - a kötés maga a munkanap-számláláshoz kell. */
  canEmberKotes?: boolean;
  /** A GLOBÁLISAN rejtett oszlopok/sorok kezelése CSAK az adminé (a
   * felhasználó kérése): ő a "Rejtettek mutatása" kapcsolóval halványítva
   * megnézheti és visszahozhatja őket - mindenki másnak tényleg eltűnnek. */
  rejtettetLatja?: boolean;
  /** A munkatársak az oszlop-ember kötéshez. */
  emberek: { id: number; nev: string }[];
  /** A bejelentkezett munkatárs SZEMÉLYES nézete (saját oszlop-elrejtés,
   * szélességek) - ezzel indul a rács, és ide mentődik vissza. */
  kezdoNezet?: DiszpoNezet;
}) {
  const router = useRouter();
  const gorgetoRef = useRef<HTMLDivElement | null>(null);
  const [gorgetes, setGorgetes] = useState({ top: 0, left: 0 });
  const [meret, setMeret] = useState({ szeles: 1200, magas: 600 });
  const [kijelolt, setKijelolt] = useState<Pont>({ sor: munkalap.fejlec_sorok, oszlop: 0 });
  const [tartomany, setTartomany] = useState<Tartomany | null>(null);
  const [huzas, setHuzas] = useState(false);
  const [szerkesztes, setSzerkesztes] = useState<{ pont: Pont; ertek: string } | null>(null);
  const [menu, setMenu] = useState<{ x: number; y: number; pont: Pont } | null>(null);
  const [fejlecMenu, setFejlecMenu] = useState<{ x: number; y: number; oszlop: number } | null>(null);
  const [busy, setBusy] = useState(false);
  // A legutóbbi Ctrl+C belső másolata: a szöveg mellett a cellák SZÍNÉT is
  // őrzi. A rendszer-vágólapra csak szöveg fér; beillesztéskor a szöveg
  // egyezéséből ismerjük fel, hogy a sajátunkat illesztik vissza - olyankor
  // a szín is megy (a felhasználó kérése).
  const belsoMasolat = useRef<{ szoveg: string; racs: CellaAdat[][] } | null>(null);
  // Ctrl+Shift+V: a következő beillesztés CSAK ÉRTÉKEKET tegyen (szín nélkül).
  const csakErtekRef = useRef(false);

  // ── HELYI CELLA-ÁLLAPOT (optimista) ──────────────────────────────────────
  // A szerkesztés ebbe ír AZONNAL - a mentés a háttérben, kötegelve megy.
  const [cellakHelyi, setCellakHelyi] = useState<Map<number, CellaAdat>>(() => {
    const t = new Map<number, CellaAdat>();
    for (const [sor, oszlop, ertek, szin] of munkalap.cellak) t.set(kulcs(sor, oszlop), { ertek, szin });
    return t;
  });

  // ── MENTÉSI SOR ──────────────────────────────────────────────────────────
  // A módosítások cellánként gyűlnek, és pár tized másodperc után EGY
  // kérésben mennek el. Hibánál a sor megmarad (a beírt tartalom nem vész
  // el), és az "Újra" gombbal vagy a következő szerkesztéssel újrapróbáljuk.
  const fuggoRef = useRef<Map<number, CellaValt>>(new Map());
  const mentesIdozito = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mentesFolyamatban = useRef(false);
  const [mentes, setMentes] = useState<"mentve" | "folyamatban" | "hiba">("mentve");
  // Az utolsó helyi szerkesztés ideje - az időzített háttér-frissítés csak
  // nyugalmi állapotban fut, hogy ne rángassa a rácsot gépelés közben.
  const utolsoValtozas = useRef(0);

  // ── VISSZAVONÁS / ÚJRA ───────────────────────────────────────────────────
  type Lepes = { elore: CellaValt[]; vissza: CellaValt[] };
  const undoRef = useRef<Lepes[]>([]);
  const redoRef = useRef<Lepes[]>([]);
  const [undoDb, setUndoDb] = useState(0);
  const [redoDb, setRedoDb] = useState(0);

  // ── SZEMÉLYES NÉZET ──────────────────────────────────────────────────────
  // Saját oszlop-elrejtés és -szélesség, az oszlop STABIL id-jén (nem az
  // idx-en, amit a beszúrás eltol). Mentése a szerverre megy, így újratöltés
  // és géppváltás után is megmarad - és csak a sajátunkat rendezi.
  const [sajatRejtett, setSajatRejtett] = useState<Set<number>>(
    () => new Set(kezdoNezet?.rejtett_oszlop_idk ?? []),
  );
  const [szelessegek, setSzelessegek] = useState<Record<number, number>>(() => {
    const t: Record<number, number> = {};
    for (const [k, v] of Object.entries(kezdoNezet?.oszlop_szelessegek ?? {})) t[Number(k)] = v;
    return t;
  });
  const nezetIdozito = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── EGYÉB FELÜLET-ÁLLAPOT ────────────────────────────────────────────────
  //: Az admin kapcsolója: a globálisan rejtett sorok/oszlopok NEKI SE
  //: látszanak alapból (ettől tűnt úgy, hogy a "rejtett" oszlop mégis ott
  //: van - a felhasználó hibajelzése), csak ha bekapcsolja - akkor halványan.
  const [rejtettMutat, setRejtettMutat] = useState(false);
  const [teljesKepernyo, setTeljesKepernyo] = useState(false);
  const [kereses, setKereses] = useState("");
  const [cimMezo, setCimMezo] = useState<string | null>(null);
  const [savDraft, setSavDraft] = useState<string | null>(null);
  // Oszlopszélesség-húzás állapota.
  const szelHuzas = useRef<{ oszlopId: number; kezdoX: number; kezdoSzel: number } | null>(null);

  const sorSzam = Math.max(munkalap.sor_szam, munkalap.sorok.length);
  const oszlopSzam = munkalap.oszlop_szam;

  const oszlopTerkep = useMemo(() => new Map(munkalap.oszlopok.map((o) => [o.idx, o])), [munkalap.oszlopok]);
  const sorTerkep = useMemo(() => new Map(munkalap.sorok.map((s) => [s.idx, s])), [munkalap.sorok]);

  // Az első oszlopok BEFAGYASZTVA: 146 oszlopnál a dátum nélkül nem lehet
  // tudni, melyik sorban vagyunk. Ahol nincs dátum-oszlop, ott egy elég.
  // TELEFONON (keskeny nézetben) csak EGY oszlop marad rögzítve.
  const keskeny = meret.szeles < 640;
  const fagyasztott = !keskeny && munkalap.sorok.some((s) => s.datum) ? 3 : 1;

  // Az oszlopok BALJA és SZÉLESSÉGE - halmozva. A rejtett oszlop 0 széles,
  // így a többi magától összecsúszik. Rejtett = az admin által MINDENKI elől
  // elrejtett (globális), VAGY a saját nézetben elrejtett. A globálisat az
  // admin a "Rejtettek mutatása" kapcsolóval hozhatja képbe (halványítva).
  const { oszlopBal, oszlopSzelessege } = useMemo(() => {
    const bal: number[] = new Array(oszlopSzam + 1);
    const szel: number[] = new Array(oszlopSzam);
    let fut = 0;
    for (let c = 0; c < oszlopSzam; c++) {
      const o = oszlopTerkep.get(c);
      bal[c] = fut;
      let s = (o && szelessegek[o.id]) || OSZLOP_SZELES;
      if (o?.rejtett && !(rejtettetLatja && rejtettMutat)) s = 0;
      // A saját elrejtés a fagyasztott oszlopokra nem érvényes (azok
      // igazítanak el), és a rejtettMutat sem hozza elő - az a globálisé.
      if (o && sajatRejtett.has(o.id) && c >= fagyasztott) s = 0;
      szel[c] = s;
      fut += s;
    }
    bal[oszlopSzam] = fut;
    return { oszlopBal: bal, oszlopSzelessege: szel };
  }, [oszlopTerkep, oszlopSzam, rejtettetLatja, rejtettMutat, sajatRejtett, szelessegek, fagyasztott]);

  const rejtettOszlopok = useMemo(
    () => munkalap.oszlopok.filter((o) => o.rejtett).sort((a, b) => a.idx - b.idx),
    [munkalap.oszlopok],
  );

  // A sorok TETEJE és MAGASSÁGA - halmozva. A globálisan rejtett sor 0 magas,
  // az admin a "Rejtettek mutatása" kapcsolóval látja (halványítva).
  const { sorTeteje, sorMagassaga, teljesMagassag } = useMemo(() => {
    const elvalasztoSorok = new Set(munkalap.sorok.filter((s) => s.elvalaszto).map((s) => s.idx));
    const rejtettSorIdxek = new Set(munkalap.sorok.filter((s) => s.rejtett).map((s) => s.idx));
    const teteje: number[] = new Array(sorSzam + 1);
    const magassaga: number[] = new Array(sorSzam);
    let fut = 0;
    for (let r = 0; r < sorSzam; r++) {
      teteje[r] = fut;
      magassaga[r] =
        rejtettSorIdxek.has(r) && !(rejtettetLatja && rejtettMutat)
          ? 0
          : elvalasztoSorok.has(r)
            ? ELVALASZTO_MAGASSAG
            : SOR_MAGASSAG;
      fut += magassaga[r];
    }
    teteje[sorSzam] = fut;
    return { sorTeteje: teteje, sorMagassaga: magassaga, teljesMagassag: fut };
  }, [munkalap.sorok, sorSzam, rejtettetLatja, rejtettMutat]);

  const rejtettSorok = useMemo(
    () => munkalap.sorok.filter((s) => s.rejtett).sort((a, b) => a.idx - b.idx),
    [munkalap.sorok],
  );

  /** Melyik sor van ezen a képpontnál - a halmozott tömbön keresve. */
  const sorAPontnal = useCallback(
    (y: number) => {
      let also = 0;
      let felso = sorSzam;
      while (also < felso) {
        const kozep = (also + felso) >> 1;
        if (sorTeteje[kozep] <= y) also = kozep + 1;
        else felso = kozep;
      }
      return Math.max(also - 1, 0);
    },
    [sorTeteje, sorSzam],
  );

  const fagyasztottSzeles = oszlopBal[Math.min(fagyasztott, oszlopSzam)] ?? 0;

  /** Melyik oszlop van ennél a (tartalombeli) képpontnál. */
  const oszlopAPontnal = useCallback(
    (x: number) => {
      let also = 0;
      let felso = oszlopSzam;
      while (also < felso) {
        const kozep = (also + felso) >> 1;
        if (oszlopBal[kozep] <= x) also = kozep + 1;
        else felso = kozep;
      }
      return Math.max(also - 1, 0);
    },
    [oszlopBal, oszlopSzam],
  );

  const cella = useCallback(
    (sor: number, oszlop: number) => cellakHelyi.get(kulcs(sor, oszlop)),
    [cellakHelyi],
  );

  // ÚJ SZERVER-ÁLLAPOT érkezett (fülváltás, sor/oszlop-művelet, időzített
  // frissítés): az alap a szerveré, rá a még el nem mentett helyi
  // módosítások - így a gépelés alatt érkező frissítés sem írja felül a
  // beírtat.
  useEffect(() => {
    const t = new Map<number, CellaAdat>();
    for (const [sor, oszlop, ertek, szin] of munkalap.cellak) t.set(kulcs(sor, oszlop), { ertek, szin });
    for (const f of fuggoRef.current.values()) {
      const k = kulcs(f.sor_idx, f.oszlop_idx);
      const el = t.get(k) ?? { ertek: null, szin: null };
      t.set(k, {
        ertek: f.ertek_valtozik ? (f.ertek ?? null) : el.ertek,
        szin: f.szin_valtozik ? (f.szin ?? null) : el.szin,
      });
    }
    setCellakHelyi(t);
  }, [munkalap]);

  // FÜLVÁLTÁSKOR minden munkalap-függő állapot nullázódik - a visszavonás és
  // a kijelölés a MÁSIK lapra vonatkozott. A még függő cella-mentések a RÉGI
  // lapra mennek el (oda tartoznak), mielőtt a sor kiürül.
  const elozoMunkalapId = useRef(munkalap.id);
  useEffect(() => {
    if (elozoMunkalapId.current !== munkalap.id && fuggoRef.current.size > 0) {
      const regiId = elozoMunkalapId.current;
      const maradek = [...fuggoRef.current.values()];
      fuggoRef.current = new Map();
      void authFetch(`/api/v1/diszpo-tabla/${regiId}/cellak`, {
        method: "PUT",
        body: JSON.stringify({ cellak: maradek }),
      }).catch(() => {});
      setMentes("mentve");
    }
    elozoMunkalapId.current = munkalap.id;
    setKijelolt({ sor: munkalap.fejlec_sorok, oszlop: 0 });
    setTartomany(null);
    setSzerkesztes(null);
    undoRef.current = [];
    redoRef.current = [];
    setUndoDb(0);
    setRedoDb(0);
    setSajatRejtett(new Set(kezdoNezet?.rejtett_oszlop_idk ?? []));
    const t: Record<number, number> = {};
    for (const [k, v] of Object.entries(kezdoNezet?.oszlop_szelessegek ?? {})) t[Number(k)] = v;
    setSzelessegek(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [munkalap.id]);

  useEffect(() => {
    const elem = gorgetoRef.current;
    if (!elem) return;
    const merj = () => setMeret({ szeles: elem.clientWidth, magas: elem.clientHeight });
    merj();
    const figyelo = new ResizeObserver(merj);
    figyelo.observe(elem);
    return () => figyelo.disconnect();
  }, [teljesKepernyo]);

  // ── MENTÉS ───────────────────────────────────────────────────────────────

  // Az időzítő a MINDENKORI mentő-függvényt hívja (ref-en át) - a useCallback
  // üres függősége miatt különben az első render lejárt munkalap-azonosítóját
  // zárná magába, és fülváltás után rossz lapra mentene.
  const mentesFuttatRef = useRef<() => Promise<void>>(async () => {});

  const mentesInditasa = useCallback(() => {
    if (mentesIdozito.current) clearTimeout(mentesIdozito.current);
    mentesIdozito.current = setTimeout(() => void mentesFuttatRef.current(), 600);
  }, []);

  async function mentesFuttatasa() {
    if (mentesFolyamatban.current) return;
    if (fuggoRef.current.size === 0) {
      setMentes("mentve");
      return;
    }
    mentesFolyamatban.current = true;
    setMentes("folyamatban");
    const kuldes = [...fuggoRef.current.entries()];
    fuggoRef.current = new Map();
    try {
      const res = await authFetch(`/api/v1/diszpo-tabla/${munkalap.id}/cellak`, {
        method: "PUT",
        body: JSON.stringify({ cellak: kuldes.map(([, v]) => v) }),
      });
      if (!res.ok) throw new Error(String(res.status));
      mentesFolyamatban.current = false;
      if (fuggoRef.current.size > 0) mentesInditasa();
      else setMentes("mentve");
    } catch {
      // A ki nem mentett módosítások VISSZAKERÜLNEK a sorba - de a közben
      // beírt (frissebb) módosítást nem írjuk felül velük.
      for (const [k, v] of kuldes) {
        const ujabb = fuggoRef.current.get(k);
        if (!ujabb) fuggoRef.current.set(k, v);
        else {
          if (v.ertek_valtozik && !ujabb.ertek_valtozik) {
            ujabb.ertek = v.ertek;
            ujabb.ertek_valtozik = true;
          }
          if (v.szin_valtozik && !ujabb.szin_valtozik) {
            ujabb.szin = v.szin;
            ujabb.szin_valtozik = true;
          }
        }
      }
      mentesFolyamatban.current = false;
      setMentes("hiba");
    }
  }
  mentesFuttatRef.current = mentesFuttatasa;

  /** Minden még függő módosítás azonnali elküldése - a szerkezeti műveletek
   * (sor/oszlop beszúrás stb.) előtt kell, mert azok az indexeket eltolják. */
  async function mentesMost() {
    if (mentesIdozito.current) clearTimeout(mentesIdozito.current);
    while (fuggoRef.current.size > 0) {
      const elotte = fuggoRef.current.size;
      await mentesFuttatasa();
      // Hibánál nem pörgünk végtelen ciklusban - a hívó dönti el, mi legyen.
      if (fuggoRef.current.size >= elotte) return false;
    }
    return true;
  }

  /** A módosítások VÉGREHAJTÁSA: helyi állapot + mentési sor + (ha kell)
   * visszavonás-napló. Minden szerkesztő út ezen megy át - a cella-szerkesztés,
   * a színezés, a törlés és a beillesztés is. */
  const vegrehajt = useCallback(
    (valtozasok: CellaValt[], naplozas = true) => {
      if (valtozasok.length === 0) return;
      if (naplozas) {
        const vissza: CellaValt[] = valtozasok.map((v) => {
          const el = cellakHelyi.get(kulcs(v.sor_idx, v.oszlop_idx));
          return {
            sor_idx: v.sor_idx,
            oszlop_idx: v.oszlop_idx,
            ertek: el?.ertek ?? null,
            ertek_valtozik: v.ertek_valtozik ?? false,
            szin: el?.szin ?? null,
            szin_valtozik: v.szin_valtozik ?? false,
          };
        });
        undoRef.current.push({ elore: valtozasok, vissza });
        if (undoRef.current.length > UNDO_MERET) undoRef.current.shift();
        redoRef.current = [];
        setUndoDb(undoRef.current.length);
        setRedoDb(0);
      }
      setCellakHelyi((prev) => {
        const t = new Map(prev);
        for (const v of valtozasok) {
          const k = kulcs(v.sor_idx, v.oszlop_idx);
          const el = t.get(k) ?? { ertek: null, szin: null };
          const uj: CellaAdat = {
            ertek: v.ertek_valtozik ? ((v.ertek ?? "").trim() || null) : el.ertek,
            szin: v.szin_valtozik ? (v.szin ?? null) : el.szin,
          };
          if (uj.ertek === null && uj.szin === null) t.delete(k);
          else t.set(k, uj);
        }
        return t;
      });
      for (const v of valtozasok) {
        const k = kulcs(v.sor_idx, v.oszlop_idx);
        const el = fuggoRef.current.get(k);
        if (!el) fuggoRef.current.set(k, { ...v });
        else {
          if (v.ertek_valtozik) {
            el.ertek = v.ertek;
            el.ertek_valtozik = true;
          }
          if (v.szin_valtozik) {
            el.szin = v.szin;
            el.szin_valtozik = true;
          }
        }
      }
      utolsoValtozas.current = Date.now();
      setMentes("folyamatban");
      mentesInditasa();
    },
    [cellakHelyi, mentesInditasa],
  );

  const visszavon = useCallback(() => {
    const lepes = undoRef.current.pop();
    if (!lepes) return;
    redoRef.current.push(lepes);
    setUndoDb(undoRef.current.length);
    setRedoDb(redoRef.current.length);
    vegrehajt(lepes.vissza, false);
  }, [vegrehajt]);

  const ujra = useCallback(() => {
    const lepes = redoRef.current.pop();
    if (!lepes) return;
    undoRef.current.push(lepes);
    setUndoDb(undoRef.current.length);
    setRedoDb(redoRef.current.length);
    vegrehajt(lepes.elore, false);
  }, [vegrehajt]);

  // Ki nem mentett módosítással ne lehessen csendben elnavigálni.
  useEffect(() => {
    function orzo(e: BeforeUnloadEvent) {
      if (fuggoRef.current.size > 0) e.preventDefault();
    }
    window.addEventListener("beforeunload", orzo);
    return () => window.removeEventListener("beforeunload", orzo);
  }, []);

  // IDŐZÍTETT HÁTTÉR-FRISSÍTÉS: másfél percenként behúzzuk a többiek
  // módosításait - de csak nyugalmi állapotban (nincs függő mentés, nem
  // szerkeszt éppen senki itt), hogy ne rángassa a rácsot.
  useEffect(() => {
    const idozito = setInterval(() => {
      if (document.visibilityState !== "visible") return;
      if (fuggoRef.current.size > 0 || szerkesztes || menu || fejlecMenu) return;
      if (Date.now() - utolsoValtozas.current < 20000) return;
      router.refresh();
    }, 90000);
    return () => clearInterval(idozito);
  });

  // ── SZEMÉLYES NÉZET MENTÉSE ──────────────────────────────────────────────

  const nezetMentes = useCallback(
    (rejtett: Set<number>, szel: Record<number, number>) => {
      if (nezetIdozito.current) clearTimeout(nezetIdozito.current);
      nezetIdozito.current = setTimeout(() => {
        void authFetch(`/api/v1/diszpo-tabla/${munkalap.id}/nezet`, {
          method: "PUT",
          body: JSON.stringify({
            rejtett_oszlop_idk: [...rejtett],
            oszlop_szelessegek: Object.fromEntries(
              Object.entries(szel).map(([k, v]) => [String(k), Math.round(v)]),
            ),
          }),
        }).catch(() => {
          /* A nézet nem adat - a következő módosítás úgyis újramenti. */
        });
      }, 800);
    },
    [munkalap.id],
  );

  const sajatRejtes = useCallback(
    (oszlopIdk: number[], rejtett: boolean) => {
      setSajatRejtett((prev) => {
        const t = new Set(prev);
        for (const id of oszlopIdk) {
          if (rejtett) t.add(id);
          else t.delete(id);
        }
        nezetMentes(t, szelessegek);
        return t;
      });
    },
    [nezetMentes, szelessegek],
  );

  // ── RÁCS-MŰVELETEK ───────────────────────────────────────────────────────

  async function hivas(utvonal: string, opciok: RequestInit): Promise<boolean> {
    setBusy(true);
    try {
      // A szerkezeti műveletek az indexeket eltolják - előbb minden függő
      // cella-mentés menjen ki, különben rossz helyre íródna.
      await mentesMost();
      const res = await authFetch(`/api/v1/diszpo-tabla/${munkalap.id}${utvonal}`, opciok);
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return false;
      }
      // A beszúrás/törlés után az indexek mások - a visszavonás-napló már
      // nem érvényes rájuk.
      undoRef.current = [];
      redoRef.current = [];
      setUndoDb(0);
      setRedoDb(0);
      router.refresh();
      return true;
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  /** A kijelölés LÁTHATÓ cellái - a rejtett (globális vagy saját) oszlopokat
   * és sorokat minden művelet kihagyja, hogy ne módosuljon semmi észrevétlenül. */
  const kijeloltCellak = useCallback((): Pont[] => {
    const t = tartomany ?? { tol: kijelolt, ig: kijelolt };
    const { sor1, sor2, oszlop1, oszlop2 } = normalizal(t);
    const pontok: Pont[] = [];
    for (let r = sor1; r <= sor2; r++) {
      if (sorMagassaga[r] === 0) continue;
      for (let c = oszlop1; c <= oszlop2; c++) {
        if (oszlopSzelessege[c] === 0) continue;
        pontok.push({ sor: r, oszlop: c });
      }
    }
    return pontok;
  }, [tartomany, kijelolt, sorMagassaga, oszlopSzelessege]);

  /** Színezés/törlés a teljes kijelölésre - helyben, egy visszavonható lépésként. */
  function szinez(szin: DiszpoSzin | null) {
    if (!canEdit) return;
    vegrehajt(
      kijeloltCellak().map((p) => ({ sor_idx: p.sor, oszlop_idx: p.oszlop, szin, szin_valtozik: true })),
    );
  }

  function tartalmatTorol() {
    if (!canEdit) return;
    vegrehajt(
      kijeloltCellak().map((p) => ({ sor_idx: p.sor, oszlop_idx: p.oszlop, ertek: null, ertek_valtozik: true })),
    );
  }

  function mentesSzoveg(pont: Pont, ertek: string) {
    vegrehajt([{ sor_idx: pont.sor, oszlop_idx: pont.oszlop, ertek: ertek || null, ertek_valtozik: true }]);
  }

  const lepj = useCallback(
    (dSor: number, dOszlop: number, kiterjeszt = false) => {
      // A 0 szélességű (rejtett) oszlopokat és 0 magasságú sorokat átugorjuk -
      // különben a kijelölés egy láthatatlan cellán állna meg.
      let celOszlop = Math.min(Math.max(kijelolt.oszlop + dOszlop, 0), oszlopSzam - 1);
      if (dOszlop !== 0) {
        const irany = dOszlop > 0 ? 1 : -1;
        while (celOszlop >= 0 && celOszlop < oszlopSzam && oszlopSzelessege[celOszlop] === 0) {
          celOszlop += irany;
        }
        if (celOszlop < 0 || celOszlop >= oszlopSzam) celOszlop = kijelolt.oszlop;
      }
      let celSor = Math.min(Math.max(kijelolt.sor + dSor, munkalap.fejlec_sorok), sorSzam - 1);
      if (dSor !== 0) {
        const sorIrany = dSor > 0 ? 1 : -1;
        while (celSor >= munkalap.fejlec_sorok && celSor < sorSzam && sorMagassaga[celSor] === 0) {
          celSor += sorIrany;
        }
        if (celSor < munkalap.fejlec_sorok || celSor >= sorSzam) celSor = kijelolt.sor;
      }
      const uj = { sor: celSor, oszlop: celOszlop };
      if (kiterjeszt) {
        setTartomany({ tol: tartomany?.tol ?? kijelolt, ig: uj });
      } else {
        setTartomany(null);
      }
      setKijelolt(uj);
      // Görgessünk oda, ha kifutott a képből - különben a nyilazás "elveszik".
      const elem = gorgetoRef.current;
      if (!elem) return;
      const y = sorTeteje[uj.sor];
      const x = oszlopBal[uj.oszlop];
      if (y < elem.scrollTop) elem.scrollTop = y;
      if (y + sorMagassaga[uj.sor] > elem.scrollTop + elem.clientHeight)
        elem.scrollTop = y + sorMagassaga[uj.sor] - elem.clientHeight;
      if (uj.oszlop >= fagyasztott) {
        if (x < elem.scrollLeft + fagyasztottSzeles) elem.scrollLeft = x - fagyasztottSzeles;
        if (x + oszlopSzelessege[uj.oszlop] > elem.scrollLeft + elem.clientWidth)
          elem.scrollLeft = x + oszlopSzelessege[uj.oszlop] - elem.clientWidth;
      }
    },
    [kijelolt, tartomany, sorSzam, oszlopSzam, munkalap.fejlec_sorok, fagyasztott, fagyasztottSzeles, oszlopBal, oszlopSzelessege, sorTeteje, sorMagassaga],
  );

  /** Ugrás egy cellára: kijelölés + odagörgetés. */
  const ugras = useCallback(
    (sor: number, oszlop: number) => {
      const s = Math.min(Math.max(sor, munkalap.fejlec_sorok), sorSzam - 1);
      const c = Math.min(Math.max(oszlop, 0), Math.max(oszlopSzam - 1, 0));
      setKijelolt({ sor: s, oszlop: c });
      setTartomany(null);
      const elem = gorgetoRef.current;
      if (!elem) return;
      elem.scrollTop = Math.max(sorTeteje[s] - elem.clientHeight / 3, 0);
      if (c >= fagyasztott) {
        const x = oszlopBal[c];
        if (x < elem.scrollLeft + fagyasztottSzeles || x > elem.scrollLeft + elem.clientWidth - 100)
          elem.scrollLeft = Math.max(x - fagyasztottSzeles - 100, 0);
      }
    },
    [munkalap.fejlec_sorok, sorSzam, oszlopSzam, sorTeteje, oszlopBal, fagyasztott, fagyasztottSzeles],
  );

  /** Ugrás a MAI naphoz (vagy a hozzá legközelebbi későbbi naphoz). */
  const ugrasMa = useCallback(() => {
    const ma = new Date();
    const maStr = `${ma.getFullYear()}-${String(ma.getMonth() + 1).padStart(2, "0")}-${String(ma.getDate()).padStart(2, "0")}`;
    const datumos = munkalap.sorok
      .filter((s) => s.datum && !s.elvalaszto && sorMagassaga[s.idx] > 0)
      .sort((a, b) => a.idx - b.idx);
    if (datumos.length === 0) return;
    const talalat = datumos.find((s) => (s.datum as string) >= maStr) ?? datumos[datumos.length - 1];
    ugras(talalat.idx, kijelolt.oszlop);
  }, [munkalap.sorok, sorMagassaga, ugras, kijelolt.oszlop]);

  // ── KERESÉS A TÁBLÁBAN ───────────────────────────────────────────────────

  const talalatok = useMemo(() => {
    const k = keresoKulcs(kereses.trim());
    if (!k) return [];
    const lista: Pont[] = [];
    for (const [cellaKulcs, adat] of cellakHelyi) {
      if (!adat.ertek) continue;
      const sor = Math.floor(cellaKulcs / 10000);
      const oszlop = cellaKulcs % 10000;
      if (sorMagassaga[sor] === 0 || oszlopSzelessege[oszlop] === 0) continue;
      if (keresoKulcs(adat.ertek).includes(k)) lista.push({ sor, oszlop });
    }
    lista.sort((a, b) => a.sor - b.sor || a.oszlop - b.oszlop);
    return lista;
  }, [kereses, cellakHelyi, sorMagassaga, oszlopSzelessege]);

  const kovetkezoTalalat = useCallback(() => {
    if (talalatok.length === 0) return;
    const utana = talalatok.find(
      (t) => t.sor > kijelolt.sor || (t.sor === kijelolt.sor && t.oszlop > kijelolt.oszlop),
    );
    const cel = utana ?? talalatok[0];
    ugras(cel.sor, cel.oszlop);
  }, [talalatok, kijelolt, ugras]);

  // ── BILLENTYŰZET ─────────────────────────────────────────────────────────
  // Ahogy a táblázatban: nyilak, Enter, Tab, F2, gépelés, Delete, Ctrl+Z/Y.
  useEffect(() => {
    function kezel(e: KeyboardEvent) {
      if (szerkesztes) return;
      const cel = e.target as HTMLElement | null;
      if (cel && (cel.tagName === "INPUT" || cel.tagName === "TEXTAREA" || cel.isContentEditable || cel.tagName === "SELECT")) return;
      if (menu) setMenu(null);
      if (fejlecMenu) setFejlecMenu(null);

      const mod = e.ctrlKey || e.metaKey;
      if (mod && (e.key === "z" || e.key === "Z")) {
        e.preventDefault();
        if (!canEdit) return;
        if (e.shiftKey) ujra();
        else visszavon();
        return;
      }
      if (mod && (e.key === "y" || e.key === "Y")) {
        e.preventDefault();
        if (canEdit) ujra();
        return;
      }
      // Ctrl+Shift+V: a KÖVETKEZŐ beillesztés csak értékeket tesz (a
      // beillesztés-esemény rögtön ez után érkezik).
      if (mod && e.shiftKey && (e.key === "v" || e.key === "V")) {
        csakErtekRef.current = true;
        setTimeout(() => {
          csakErtekRef.current = false;
        }, 500);
        return;
      }

      if (e.key === "ArrowDown") return void (e.preventDefault(), lepj(1, 0, e.shiftKey));
      if (e.key === "ArrowUp") return void (e.preventDefault(), lepj(-1, 0, e.shiftKey));
      if (e.key === "ArrowLeft") return void (e.preventDefault(), lepj(0, -1, e.shiftKey));
      if (e.key === "ArrowRight") return void (e.preventDefault(), lepj(0, 1, e.shiftKey));
      if (e.key === "Tab") return void (e.preventDefault(), lepj(0, e.shiftKey ? -1 : 1));
      if (e.key === "Enter" || e.key === "F2") {
        e.preventDefault();
        if (canEdit) setSzerkesztes({ pont: kijelolt, ertek: cella(kijelolt.sor, kijelolt.oszlop)?.ertek ?? "" });
        return;
      }
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        if (canEdit) tartalmatTorol();
        return;
      }
      if (e.key === "Escape") {
        if (tartomany) setTartomany(null);
        else if (teljesKepernyo) setTeljesKepernyo(false);
        return;
      }
      // Gépelés: azonnal szerkesztés, a leütött karakterrel - mint a Sheetsben.
      if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (!canEdit) return;
        e.preventDefault();
        setSzerkesztes({ pont: kijelolt, ertek: e.key });
      }
    }
    window.addEventListener("keydown", kezel);
    return () => window.removeEventListener("keydown", kezel);
  });

  // ── MÁSOLÁS / BEILLESZTÉS ────────────────────────────────────────────────

  /** A kijelölés LÁTHATÓ tartalma tab/soremelés tagolású szövegként + a
   * színrács a belső másolathoz. */
  const masolatKeszit = useCallback(() => {
    const t = tartomany ?? { tol: kijelolt, ig: kijelolt };
    const { sor1, sor2, oszlop1, oszlop2 } = normalizal(t);
    const sorIdxek: number[] = [];
    for (let r = sor1; r <= sor2; r++) if (sorMagassaga[r] > 0) sorIdxek.push(r);
    const oszlopIdxek: number[] = [];
    for (let c = oszlop1; c <= oszlop2; c++) if (oszlopSzelessege[c] > 0) oszlopIdxek.push(c);
    if (sorIdxek.length === 0 || oszlopIdxek.length === 0) return null;
    const racs = sorIdxek.map((r) =>
      oszlopIdxek.map((c) => {
        const cl = cella(r, c);
        return { ertek: cl?.ertek ?? null, szin: cl?.szin ?? null };
      }),
    );
    const szoveg = racs.map((sor) => sor.map((x) => x.ertek ?? "").join("\t")).join("\n");
    return { szoveg, racs };
  }, [tartomany, kijelolt, sorMagassaga, oszlopSzelessege, cella]);

  useEffect(() => {
    function masol(e: ClipboardEvent) {
      if (szerkesztes) return;
      const cel = e.target as HTMLElement | null;
      if (cel && (cel.tagName === "INPUT" || cel.tagName === "TEXTAREA" || cel.isContentEditable)) return;
      const masolat = masolatKeszit();
      if (!masolat) return;
      e.clipboardData?.setData("text/plain", masolat.szoveg);
      e.preventDefault();
      belsoMasolat.current = masolat;
    }
    window.addEventListener("copy", masol);
    return () => window.removeEventListener("copy", masol);
  });

  /** Beillesztés a kijelölt cellától jobbra-lefelé, a LÁTHATÓ cellákba. A
   * saját (Ctrl+C-s) másolatnál a szín is megy; `csakErtek` esetén soha.
   * EGY visszavonható lépés - egy tömeges beillesztés egy Ctrl+Z. */
  const beillesztes = useCallback(
    (szoveg: string, csakErtek: boolean) => {
      if (!canEdit) return;
      const normalizalt = szoveg.replace(/\r/g, "").replace(/\n$/, "");
      if (!normalizalt) return;
      const sorok = normalizalt.split("\n").map((sor) => sor.split("\t"));
      const belso = belsoMasolat.current;
      const szines = !csakErtek && belso !== null && belso.szoveg === normalizalt ? belso : null;
      const celOszlopok: number[] = [];
      for (let c = kijelolt.oszlop; c < oszlopSzam; c++) {
        if (oszlopSzelessege[c] > 0) celOszlopok.push(c);
      }
      const celSorok: number[] = [];
      for (let r = kijelolt.sor; r < sorSzam; r++) {
        if (sorMagassaga[r] > 0) celSorok.push(r);
      }
      const cellak: CellaValt[] = [];
      sorok.forEach((ertekek, dr) => {
        const r = celSorok[dr];
        if (r === undefined) return;
        ertekek.forEach((ertek, dc) => {
          const c = celOszlopok[dc];
          if (c === undefined) return;
          cellak.push({
            sor_idx: r,
            oszlop_idx: c,
            ertek: ertek.trim() || null,
            ertek_valtozik: true,
            ...(szines ? { szin: szines.racs[dr]?.[dc]?.szin ?? null, szin_valtozik: true } : {}),
          });
        });
      });
      vegrehajt(cellak);
    },
    [canEdit, kijelolt, oszlopSzam, sorSzam, oszlopSzelessege, sorMagassaga, vegrehajt],
  );

  useEffect(() => {
    function beilleszt(e: ClipboardEvent) {
      if (!canEdit || szerkesztes) return;
      const cel = e.target as HTMLElement | null;
      // Szerkesztő-inputba az input natív beillesztése dolgozik, azt nem
      // vesszük el.
      if (cel && (cel.tagName === "INPUT" || cel.tagName === "TEXTAREA" || cel.isContentEditable)) return;
      const szoveg = e.clipboardData?.getData("text/plain");
      if (!szoveg) return;
      e.preventDefault();
      beillesztes(szoveg, csakErtekRef.current);
      csakErtekRef.current = false;
    }
    window.addEventListener("paste", beilleszt);
    return () => window.removeEventListener("paste", beilleszt);
  });

  // ── OSZLOPSZÉLESSÉG ──────────────────────────────────────────────────────

  useEffect(() => {
    function mozgat(e: PointerEvent) {
      const h = szelHuzas.current;
      if (!h) return;
      const uj = Math.min(Math.max(h.kezdoSzel + (e.clientX - h.kezdoX), OSZLOP_MIN), OSZLOP_MAX);
      setSzelessegek((prev) => ({ ...prev, [h.oszlopId]: uj }));
    }
    function enged() {
      if (!szelHuzas.current) return;
      szelHuzas.current = null;
      setSzelessegek((prev) => {
        nezetMentes(sajatRejtett, prev);
        return prev;
      });
    }
    window.addEventListener("pointermove", mozgat);
    window.addEventListener("pointerup", enged);
    return () => {
      window.removeEventListener("pointermove", mozgat);
      window.removeEventListener("pointerup", enged);
    };
  }, [nezetMentes, sajatRejtett]);

  /** Szélesség igazítása a tartalomhoz (dupla katt a húzófülre) - a leghosszabb
   * cellatartalmat mérjük meg, mint a táblázatkezelők. */
  const tartalomhozIgazit = useCallback(
    (oszlopIdx: number) => {
      const o = oszlopTerkep.get(oszlopIdx);
      if (!o) return;
      const vaszon = document.createElement("canvas").getContext("2d");
      if (!vaszon) return;
      vaszon.font =
        '12px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
      let max = vaszon.measureText(o.cimke ?? "").width;
      for (const [cellaKulcs, adat] of cellakHelyi) {
        if (cellaKulcs % 10000 !== oszlopIdx || !adat.ertek) continue;
        const szeles = vaszon.measureText(adat.ertek).width;
        if (szeles > max) max = szeles;
      }
      const uj = Math.min(Math.max(Math.ceil(max) + 18, 60), OSZLOP_MAX);
      setSzelessegek((prev) => {
        const t = { ...prev, [o.id]: uj };
        nezetMentes(sajatRejtett, t);
        return t;
      });
    },
    [oszlopTerkep, cellakHelyi, nezetMentes, sajatRejtett],
  );

  // ── LÁTHATÓ ABLAK ────────────────────────────────────────────────────────

  const elsoSor = Math.max(munkalap.fejlec_sorok, sorAPontnal(gorgetes.top) - RATARTAS);
  const utolsoSor = Math.min(sorSzam, sorAPontnal(gorgetes.top + meret.magas) + RATARTAS + 1);
  const elsoOszlop = Math.max(fagyasztott, oszlopAPontnal(gorgetes.left + fagyasztottSzeles) - RATARTAS);
  const utolsoOszlop = Math.min(oszlopSzam, oszlopAPontnal(gorgetes.left + meret.szeles) + RATARTAS + 1);

  const lathatoSorok: number[] = [];
  for (let r = elsoSor; r < utolsoSor; r++) lathatoSorok.push(r);
  const lathatoOszlopok: number[] = [];
  for (let c = elsoOszlop; c < utolsoOszlop; c++) lathatoOszlopok.push(c);
  const fagyasztottOszlopok: number[] = [];
  for (let c = 0; c < Math.min(fagyasztott, oszlopSzam); c++) fagyasztottOszlopok.push(c);
  const fejlecSorok: number[] = [];
  for (let r = 0; r < munkalap.fejlec_sorok; r++) fejlecSorok.push(r);

  function cellaStilus(szin: string | null | undefined): React.CSSProperties {
    if (!szin || !(szin in SZIN_LEIRAS)) return {};
    const s = SZIN_LEIRAS[szin as DiszpoSzin];
    // Az "üres" jelölés nem fest ki semmit: pont az a lényege, hogy úgy
    // nézzen ki, mint egy érintetlen cella (lásd lib/diszpoSzin.ts).
    if (s.jelolt) return {};
    return { backgroundColor: s.hatter, color: s.szoveg };
  }

  function kijeloltE(sor: number, oszlop: number): boolean {
    if (!tartomany) return kijelolt.sor === sor && kijelolt.oszlop === oszlop;
    const { sor1, sor2, oszlop1, oszlop2 } = normalizal(tartomany);
    return sor >= sor1 && sor <= sor2 && oszlop >= oszlop1 && oszlop <= oszlop2;
  }

  /** Egy cella kirajzolása - abszolút pozícióval (a virtualizálás miatt).
   *
   * A BEFAGYASZTOTT oszlopok cellái nem itt kapják a "balra tapadó" helyüket
   * - azt a hívó (a `frz` csomópont, lásd lent) adja valódi CSS
   * `position: sticky`-vel. Itt a `left` ezért a fagyasztott oszlopoknál is
   * csak a saját, belső (a csomóponton belüli) vízszintes helyzet. */
  function Cella({ sor, oszlop, fagyott }: { sor: number; oszlop: number; fagyott: boolean }) {
    const c = cella(sor, oszlop);
    const s = sorTerkep.get(sor);
    if (oszlopSzelessege[oszlop] === 0 || sorMagassaga[sor] === 0) return null;
    const szerkesztettE = szerkesztes?.pont.sor === sor && szerkesztes?.pont.oszlop === oszlop;
    const bal = oszlopBal[oszlop];
    const uresJelolt = c?.szin === "feher";
    const aktivE = kijelolt.sor === sor && kijelolt.oszlop === oszlop;
    // Az admin a "Rejtettek mutatása" mellett a GLOBÁLISAN rejtett oszlopot/
    // sort is látja, de halványítva - így látszik, hogy a többiek nem látják.
    const rejtveDeLatszik = rejtettetLatja && rejtettMutat && !!(oszlopTerkep.get(oszlop)?.rejtett || s?.rejtett);
    return (
      <div
        style={{
          position: "absolute",
          top: sorTeteje[sor],
          left: bal,
          width: oszlopSzelessege[oszlop],
          height: sorMagassaga[sor],
          zIndex: fagyott ? 2 : undefined,
          ...cellaStilus(c?.szin),
        }}
        className={`relative overflow-hidden border-b border-r border-border px-1.5 text-[12px] leading-[24px] ${
          s?.elvalaszto ? "bg-surface-3 font-medium" : ""
        } ${aktivE ? "outline outline-2 -outline-offset-2 outline-text-accent" : ""} ${
          // A fagyasztott oszlopnak MINDIG kell átlátszatlan háttér, különben
          // görgetéskor a mögötte (a rács tartalmában) elhaladó, színes sorok
          // átütnének rajta. Az "üresen hagyva" jelölés (feher) szándékosan
          // nem fest hátteret (lásd cellaStilus) - itt ezért külön kezeljük.
          fagyott && (!c?.szin || uresJelolt) ? "bg-surface-2" : ""
        } ${rejtveDeLatszik ? "opacity-50" : ""}`}
        onPointerDown={(e) => {
          // ÉRINTŐKIJELZŐN nincs dupla katt és billentyűzet sem, amivel a
          // szerkesztés elindulna (a felhasználó jelzése: telefonról nem
          // lehetett írni a táblába). A Google Táblázatok mintája: az első
          // koppintás kijelöl, a MÁR KIJELÖLT cellára koppintás szerkeszt.
          if (e.pointerType !== "touch" || !canEdit || szerkesztettE) return;
          if (kijelolt.sor === sor && kijelolt.oszlop === oszlop) {
            e.preventDefault();
            setTartomany(null);
            setSzerkesztes({ pont: { sor, oszlop }, ertek: c?.ertek ?? "" });
          }
        }}
        onMouseDown={(e) => {
          if (e.button === 2) return;
          if (e.shiftKey) setTartomany({ tol: tartomany?.tol ?? kijelolt, ig: { sor, oszlop } });
          else {
            setKijelolt({ sor, oszlop });
            setTartomany(null);
            setHuzas(true);
          }
        }}
        onMouseEnter={() => huzas && setTartomany({ tol: kijelolt, ig: { sor, oszlop } })}
        onDoubleClick={() => canEdit && setSzerkesztes({ pont: { sor, oszlop }, ertek: c?.ertek ?? "" })}
        onContextMenu={(e) => {
          e.preventDefault();
          if (!kijeloltE(sor, oszlop)) {
            setKijelolt({ sor, oszlop });
            setTartomany(null);
          }
          setMenu({ x: e.clientX, y: e.clientY, pont: { sor, oszlop } });
        }}
        title={c?.ertek ?? undefined}
      >
        {/* A TARTOMÁNY jelölése: halvány fátyol - az aktív cella a keretes. */}
        {!aktivE && kijeloltE(sor, oszlop) && (
          <span className="pointer-events-none absolute inset-0 bg-text-accent/15" />
        )}
        {szerkesztettE ? (
          <input
            autoFocus
            value={szerkesztes.ertek}
            onChange={(e) => setSzerkesztes({ ...szerkesztes, ertek: e.target.value })}
            onBlur={() => {
              mentesSzoveg(szerkesztes.pont, szerkesztes.ertek);
              setSzerkesztes(null);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === "Tab") {
                e.preventDefault();
                mentesSzoveg(szerkesztes.pont, szerkesztes.ertek);
                setSzerkesztes(null);
                lepj(e.key === "Enter" ? 1 : 0, e.key === "Tab" ? 1 : 0);
              }
              if (e.key === "Escape") {
                e.stopPropagation();
                setSzerkesztes(null);
              }
            }}
            className="h-full w-full bg-surface-1 text-[12px] text-text-primary outline-none"
          />
        ) : (
          <>
            <span className="block truncate">{c?.ertek ?? ""}</span>
            {/* Az "üresen hagyva" jelölés halvány sarok-jele: enélkül nem
                lehetne megkülönböztetni egy tényleg érintetlen cellától -
                pedig ez MUNKANAPNAK számít. */}
            {uresJelolt && (
              <span
                aria-hidden
                title="Üresen hagyva – munkanap volt, de nem kapott munkát"
                className="pointer-events-none absolute bottom-[3px] left-[3px] h-1 w-1 rounded-full bg-text-muted opacity-70"
              />
            )}
          </>
        )}
      </div>
    );
  }

  const kijeloltOszlop = oszlopTerkep.get(kijelolt.oszlop);
  const kijeloltSor = sorTerkep.get(kijelolt.sor);
  const aktivCella = cella(kijelolt.sor, kijelolt.oszlop);

  // Az Oszlopok panel tételei.
  const panelOszlopok: OszlopTetel[] = useMemo(
    () =>
      munkalap.oszlopok.map((o) => ({
        id: o.id,
        idx: o.idx,
        betu: oszlopBetu(o.idx),
        cimke: o.cimke,
        employee_nev: o.employee_nev,
        globalisRejtett: o.rejtett,
        sajatRejtett: sajatRejtett.has(o.id),
        fagyasztott: o.idx < fagyasztott,
      })),
    [munkalap.oszlopok, sajatRejtett, fagyasztott],
  );

  /** A fejléc-menü cél-oszlopai: ha a kattintott oszlop benne áll a kijelölt
   * tartományban, az EGÉSZ (látható, nem fagyasztott) oszlop-sáv - így több
   * oszlop egyszerre rejthető el. */
  const fejlecMenuOszlopai = useCallback(
    (oszlop: number): number[] => {
      if (tartomany) {
        const { oszlop1, oszlop2 } = normalizal(tartomany);
        if (oszlop >= oszlop1 && oszlop <= oszlop2) {
          const lista: number[] = [];
          for (let c = Math.max(oszlop1, fagyasztott); c <= oszlop2; c++) {
            if (oszlopSzelessege[c] > 0) lista.push(c);
          }
          return lista;
        }
      }
      return oszlop >= fagyasztott && oszlopSzelessege[oszlop] > 0 ? [oszlop] : [];
    },
    [tartomany, fagyasztott, oszlopSzelessege],
  );

  /** A közvetlenül egy oszlop ELŐTT rejlő (0 széles) oszlopok - a fejlécben
   * ide kerül a finom jelölés, ahonnan visszahozhatók. A globálisan rejtettet
   * csak az admin kapja jelölésként (másnak azt nem szabad elárulni). */
  const rejtettElotte = useCallback(
    (oszlop: number): { sajat: number[]; globalis: number[] } => {
      const sajat: number[] = [];
      const globalis: number[] = [];
      for (let c = oszlop - 1; c >= fagyasztott && oszlopSzelessege[c] === 0; c--) {
        const o = oszlopTerkep.get(c);
        if (!o) continue;
        if (sajatRejtett.has(o.id)) sajat.push(o.id);
        else if (o.rejtett && rejtettetLatja) globalis.push(c);
      }
      return { sajat, globalis };
    },
    [fagyasztott, oszlopSzelessege, oszlopTerkep, sajatRejtett, rejtettetLatja],
  );

  const vanSajatBeallitas = sajatRejtett.size > 0 || Object.keys(szelessegek).length > 0;

  const racsMagassag = teljesKepernyo ? "calc(100vh - 132px)" : "68vh";

  return (
    <div
      className={
        teljesKepernyo
          ? "fixed inset-0 z-50 flex flex-col gap-2 overflow-auto bg-surface-1 p-3"
          : "space-y-2"
      }
      onMouseUp={() => setHuzas(false)}
    >
      {/* ESZKÖZTÁR: visszavonás, színezés, sor/oszlop, oszlopok, keresés, nézet. */}
      <div className="flex flex-wrap items-center gap-1.5">
        {canEdit && (
          <>
            <button
              type="button"
              disabled={undoDb === 0}
              title="Visszavonás (Ctrl+Z)"
              onClick={visszavon}
              className="rounded-[var(--radius)] border border-border p-1.5 text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              <Undo2 size={14} />
            </button>
            <button
              type="button"
              disabled={redoDb === 0}
              title="Újra (Ctrl+Y vagy Ctrl+Shift+Z)"
              onClick={ujra}
              className="rounded-[var(--radius)] border border-border p-1.5 text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              <Redo2 size={14} />
            </button>
            <span className="mx-0.5 h-4 w-px bg-border" />
            {DISZPO_SZINEK.map((szin) => (
              <button
                key={szin}
                type="button"
                title={SZIN_LEIRAS[szin].jelentes}
                onClick={() => szinez(szin)}
                style={{ backgroundColor: SZIN_LEIRAS[szin].hatter, color: SZIN_LEIRAS[szin].szoveg }}
                className="rounded-[var(--radius)] px-2.5 py-1 text-[12px] font-medium"
              >
                {SZIN_LEIRAS[szin].cimke}
              </button>
            ))}
            <button
              type="button"
              onClick={() => szinez(null)}
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3"
            >
              Szín törlése
            </button>
            <span className="mx-0.5 h-4 w-px bg-border" />
            <button
              type="button"
              disabled={busy}
              onClick={() => hivas("/sor", { method: "POST", body: JSON.stringify({ idx: kijelolt.sor }) })}
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              + Sor fölé
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                hivas("/sor", { method: "POST", body: JSON.stringify({ idx: kijelolt.sor, ala: true }) })
              }
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              + Sor alá
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                hivas("/oszlop", { method: "POST", body: JSON.stringify({ idx: kijelolt.oszlop, ala: true }) })
              }
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              + Oszlop
            </button>
            <span className="mx-0.5 h-4 w-px bg-border" />
          </>
        )}
        <DiszpoOszlopValaszto
          oszlopok={panelOszlopok}
          onSajatValt={(id, rejtett) => sajatRejtes([id], rejtett)}
          onOsszesMutat={() => sajatRejtes([...sajatRejtett], false)}
          onAlapnezet={() => {
            setSajatRejtett(new Set());
            setSzelessegek({});
            nezetMentes(new Set(), {});
          }}
          vanSajatBeallitas={vanSajatBeallitas}
        />
        <div className="flex items-center gap-1 rounded-[var(--radius)] border border-border px-2 py-1">
          <Search size={12} className="shrink-0 text-text-muted" />
          <input
            value={kereses}
            onChange={(e) => setKereses(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                kovetkezoTalalat();
              }
              if (e.key === "Escape") {
                setKereses("");
                (e.target as HTMLInputElement).blur();
              }
            }}
            placeholder="Keresés a táblában…"
            className="w-[130px] bg-transparent text-[12px] text-text-primary outline-none placeholder:text-text-muted"
          />
          {kereses.trim() && (
            <button
              type="button"
              onClick={kovetkezoTalalat}
              title="Következő találat (Enter)"
              className="shrink-0 text-[11px] text-text-muted hover:text-text-primary"
            >
              {talalatok.length} db
            </button>
          )}
        </div>
        <button
          type="button"
          onClick={ugrasMa}
          title="Ugrás a mai naphoz"
          className="flex items-center gap-1 rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3"
        >
          <CalendarDays size={13} />
          Ma
        </button>
        {rejtettetLatja && (rejtettOszlopok.length > 0 || rejtettSorok.length > 0 || rejtettMutat) && (
          <button
            type="button"
            onClick={() => setRejtettMutat((m) => !m)}
            title={
              rejtettMutat
                ? "A mindenki elől rejtett sorok/oszlopok elrejtése nálad is"
                : "A mindenki elől rejtett sorok/oszlopok megmutatása (halványítva, csak neked)"
            }
            className={`flex items-center gap-1 rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] hover:bg-surface-3 ${
              rejtettMutat ? "text-text-accent" : "text-text-secondary"
            }`}
          >
            {rejtettMutat ? <Eye size={13} /> : <EyeOff size={13} />}
            Rejtettek
          </button>
        )}
        <button
          type="button"
          onClick={() => setTeljesKepernyo((t) => !t)}
          title={teljesKepernyo ? "Kilépés a teljes képernyőből (Esc)" : "Teljes képernyős tábla"}
          className="rounded-[var(--radius)] border border-border p-1.5 text-text-secondary hover:bg-surface-3"
        >
          {teljesKepernyo ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
        </button>
        {/* MENTÉS-ÁLLAPOT: mindig látszik, mi a helyzet - hibánál a beírt
            tartalom helyben marad, és újra lehet próbálni. */}
        <span className="ml-auto flex items-center gap-2">
          {mentes === "hiba" ? (
            <button
              type="button"
              onClick={() => void mentesFuttatasa()}
              className="rounded-[var(--radius)] border border-text-danger/60 bg-text-danger/10 px-2.5 py-1 text-[12px] font-medium text-text-danger"
            >
              Sikertelen mentés – Újra
            </button>
          ) : (
            <span className={`text-[11.5px] ${mentes === "folyamatban" ? "text-text-accent" : "text-text-muted"}`}>
              {mentes === "folyamatban" ? "Mentés…" : "Mentve ✓"}
            </span>
          )}
        </span>
      </div>

      {/* CELLACÍM-MEZŐ ÉS SZERKESZTŐSÁV - mint a táblázatkezelőkben: hosszú
          cellatartalom kényelmes olvasása/írása, és címre ("C42") ugrás. */}
      <div className="flex items-center gap-1.5">
        <input
          value={cimMezo ?? `${oszlopBetu(kijelolt.oszlop)}${kijelolt.sor + 1}`}
          onFocus={(e) => {
            setCimMezo(e.currentTarget.value);
            e.currentTarget.select();
          }}
          onChange={(e) => setCimMezo(e.target.value)}
          onBlur={() => setCimMezo(null)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              const p = cimbolPont((e.target as HTMLInputElement).value);
              if (p) ugras(p.sor, p.oszlop);
              setCimMezo(null);
              (e.target as HTMLInputElement).blur();
            }
            if (e.key === "Escape") {
              setCimMezo(null);
              (e.target as HTMLInputElement).blur();
            }
          }}
          title="Cellacím – írj be egy címet (pl. C42) és nyomj Entert az ugráshoz"
          className="w-[76px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-center font-mono text-[12px] text-text-primary focus:outline-none"
        />
        <span className="text-[11px] text-text-muted">fx</span>
        <input
          value={savDraft ?? aktivCella?.ertek ?? ""}
          disabled={!canEdit}
          onChange={(e) => setSavDraft(e.target.value)}
          onBlur={() => {
            if (savDraft !== null && savDraft !== (aktivCella?.ertek ?? "")) {
              mentesSzoveg(kijelolt, savDraft);
            }
            setSavDraft(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (savDraft !== null) mentesSzoveg(kijelolt, savDraft);
              setSavDraft(null);
              (e.target as HTMLInputElement).blur();
              lepj(1, 0);
            }
            if (e.key === "Escape") {
              setSavDraft(null);
              (e.target as HTMLInputElement).blur();
            }
          }}
          placeholder={canEdit ? "A kijelölt cella tartalma…" : ""}
          className="min-w-0 flex-1 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12.5px] text-text-primary focus:outline-none disabled:opacity-60"
        />
        <span className="hidden text-[11.5px] text-text-muted sm:block">
          {kijeloltOszlop?.cimke ? `${kijeloltOszlop.cimke}` : ""}
          {kijeloltSor?.datum ? ` · ${kijeloltSor.datum}` : ""}
          {tartomany ? ` · ${kijeloltCellak().length} cella` : ""}
        </span>
      </div>

      {/* A GLOBÁLISAN rejtett oszlopok visszahozása (admin): felsoroljuk őket,
          egy kattintás újra megjeleníti - mindenkinek. */}
      {rejtettetLatja && rejtettOszlopok.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[12px]">
          <span className="text-text-secondary" title="Ezeket az admin mindenki elől elrejtette">
            Mindenki elől rejtett oszlopok ({rejtettOszlopok.length}):
          </span>
          {rejtettOszlopok.map((o) => (
            <button
              key={o.idx}
              type="button"
              disabled={busy || !canEdit}
              title="Oszlop megjelenítése mindenkinek"
              onClick={() =>
                hivas(`/oszlop/${o.idx}`, { method: "PUT", body: JSON.stringify({ rejtett: false }) })
              }
              className="rounded-[var(--radius)] border border-border px-2 py-0.5 text-text-secondary hover:bg-surface-2 disabled:opacity-40"
            >
              {oszlopBetu(o.idx)}
              {o.cimke ? ` · ${o.cimke}` : ""} ×
            </button>
          ))}
        </div>
      )}

      {/* A GLOBÁLISAN rejtett sorok visszahozása - ugyanaz, mint az oszlopoknál. */}
      {rejtettetLatja && rejtettSorok.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[12px]">
          <span className="text-text-secondary">Mindenki elől rejtett sorok ({rejtettSorok.length}):</span>
          {rejtettSorok.map((s) => (
            <button
              key={s.idx}
              type="button"
              disabled={busy || !canEdit}
              title="Sor megjelenítése mindenkinek"
              onClick={() => hivas(`/sor/${s.idx}`, { method: "PUT", body: JSON.stringify({ rejtett: false }) })}
              className="rounded-[var(--radius)] border border-border px-2 py-0.5 text-text-secondary hover:bg-surface-2 disabled:opacity-40"
            >
              {s.idx + 1}.{s.datum ? ` · ${s.datum}` : ""} ×
            </button>
          ))}
        </div>
      )}

      {/* Az oszlop-ember kötés: enélkül az oszlop színei nem számítanak bele a
          munkanap-számlálásba (lásd backend routes/diszpo_tabla.py). CSAK az
          admin látja (a felhasználó kérése), és csak a diszpó-jellegű (két
          fejléc-soros) munkalapokon van értelme. */}
      {canEmberKotes && canEdit && munkalap.fejlec_sorok > 1 && kijeloltOszlop && (
        <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[12.5px]">
          <span className="text-text-secondary">
            „{kijeloltOszlop.cimke ?? oszlopBetu(kijelolt.oszlop)}” oszlop munkatársa:
          </span>
          <KeresosSelect
            value={kijeloltOszlop.employee_id != null ? String(kijeloltOszlop.employee_id) : ""}
            options={[
              { value: "", label: "– nincs hozzákötve –" },
              ...emberek.map((emb) => ({ value: String(emb.id), label: emb.nev })),
            ]}
            disabled={busy}
            onChange={(uj) =>
              void hivas(`/oszlop/${kijelolt.oszlop}`, {
                method: "PUT",
                body: JSON.stringify({ employee_id: uj ? Number(uj) : null }),
              })
            }
            className="min-w-[220px]"
          />
          {!kijeloltOszlop.employee_id && (
            <span className="text-text-warning">
              Kötés nélkül ennek az oszlopnak a napjai nem számítanak bele a munkanap-számlálásba.
            </span>
          )}
        </div>
      )}

      {/* A RÁCS. A görgető a teljes méretet mutatja, de csak a látható ablakot
          rajzoljuk ki (lásd a komponens leírását). */}
      <div className="relative rounded-[var(--radius)] border border-border">
        {/* OSZLOPFEJLÉC (A, B, C…) - a görgetéssel együtt mozog vízszintesen.
            Jobb kattintásra oszlop-menü (elrejtés, szélesség, beszúrás), a
            jobb szélén szélesség-húzó fül. */}
        <div
          className="relative overflow-hidden border-b border-border bg-surface-3"
          style={{ height: OSZLOPFEJ_MAGAS, marginLeft: SORFEJ_SZELES }}
        >
          {[...fagyasztottOszlopok, ...lathatoOszlopok].map((c) => {
            if (oszlopSzelessege[c] === 0) return null;
            const fagyott = c < fagyasztott;
            const bal = fagyott ? oszlopBal[c] + gorgetes.left : oszlopBal[c];
            const o = oszlopTerkep.get(c);
            const elotte = rejtettElotte(c);
            const vanJeloles = elotte.sajat.length + elotte.globalis.length > 0;
            return (
              <div
                key={c}
                style={{ position: "absolute", left: bal - gorgetes.left, width: oszlopSzelessege[c], zIndex: fagyott ? 2 : 1 }}
                onClick={() => setTartomany({ tol: { sor: munkalap.fejlec_sorok, oszlop: c }, ig: { sor: sorSzam - 1, oszlop: c } })}
                onContextMenu={(e) => {
                  e.preventDefault();
                  // Ha a kattintott oszlop a kijelölt tartományon KÍVÜL esik,
                  // a kijelölés rá ugrik - tartományon belül megmarad, hogy a
                  // menü több oszlopra szólhasson.
                  const benne =
                    tartomany &&
                    (() => {
                      const { oszlop1, oszlop2 } = normalizal(tartomany);
                      return c >= oszlop1 && c <= oszlop2;
                    })();
                  if (!benne) {
                    setKijelolt({ sor: kijelolt.sor, oszlop: c });
                    setTartomany(null);
                  }
                  setFejlecMenu({ x: e.clientX, y: e.clientY, oszlop: c });
                }}
                title={o?.cimke ? `${oszlopBetu(c)} · ${o.cimke}` : oszlopBetu(c)}
                className={`h-[24px] cursor-pointer select-none border-r border-border bg-surface-3 text-center text-[10.5px] leading-[24px] ${
                  kijelolt.oszlop === c ? "text-text-accent" : "text-text-muted"
                }`}
              >
                {oszlopBetu(c)}
                {/* FINOM JELÖLÉS: itt rejtett oszlop(ok) lapulnak - kattintásra
                    visszajönnek (a felhasználó kérése). */}
                {vanJeloles && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (elotte.sajat.length > 0) sajatRejtes(elotte.sajat, false);
                      for (const gIdx of elotte.globalis) {
                        void hivas(`/oszlop/${gIdx}`, { method: "PUT", body: JSON.stringify({ rejtett: false }) });
                      }
                    }}
                    title={`${elotte.sajat.length + elotte.globalis.length} rejtett oszlop megjelenítése`}
                    className="absolute -left-[1px] top-0 h-full w-[7px] border-l-2 border-dotted border-text-accent bg-bg-accent hover:w-[10px]"
                  />
                )}
                {/* SZÉLESSÉG-HÚZÓ FÜL: húzásra átméretez, dupla kattintásra a
                    tartalomhoz igazít - csak a saját nézetet állítja. */}
                <div
                  onPointerDown={(e) => {
                    if (!o) return;
                    e.preventDefault();
                    e.stopPropagation();
                    szelHuzas.current = {
                      oszlopId: o.id,
                      kezdoX: e.clientX,
                      kezdoSzel: oszlopSzelessege[c],
                    };
                  }}
                  onDoubleClick={(e) => {
                    e.stopPropagation();
                    tartalomhozIgazit(c);
                  }}
                  onClick={(e) => e.stopPropagation()}
                  title="Húzd az átméretezéshez, dupla kattintás: igazítás a tartalomhoz"
                  className="absolute right-0 top-0 h-full w-[6px] cursor-col-resize hover:bg-text-accent/40"
                />
              </div>
            );
          })}
        </div>

        <div className="flex">
          {/* SORFEJLÉC (1, 2, 3…) */}
          <div
            className="relative shrink-0 overflow-hidden border-r border-border bg-surface-3"
            style={{ width: SORFEJ_SZELES, height: meret.magas }}
          >
            {[...fejlecSorok, ...lathatoSorok].map((r) => {
              if (sorMagassaga[r] === 0) return null;
              return (
                <div
                  key={r}
                  style={{
                    position: "absolute",
                    top: sorTeteje[r] - (r < munkalap.fejlec_sorok ? 0 : gorgetes.top),
                    height: sorMagassaga[r],
                  }}
                  onClick={() => setTartomany({ tol: { sor: r, oszlop: 0 }, ig: { sor: r, oszlop: oszlopSzam - 1 } })}
                  className={`w-full cursor-pointer border-b border-border text-center text-[10.5px] leading-[25px] ${
                    kijelolt.sor === r ? "text-text-accent" : "text-text-muted"
                  } ${r < munkalap.fejlec_sorok ? "z-10 bg-surface-3" : ""}`}
                >
                  {r + 1}
                </div>
              );
            })}
          </div>

          <div
            ref={gorgetoRef}
            onScroll={(e) =>
              setGorgetes({ top: e.currentTarget.scrollTop, left: e.currentTarget.scrollLeft })
            }
            onContextMenu={(e) => e.preventDefault()}
            className="relative flex-1 overflow-auto"
            style={{ height: racsMagassag }}
          >
            {/* A teljes méret - ettől lesz igazi a görgetősáv. */}
            <div
              style={{
                width: oszlopBal[oszlopSzam],
                height: teljesMagassag,
                position: "relative",
              }}
            >
              {/* FEJLÉC-SOROK: fent ragadnak. */}
              {fejlecSorok.map((r) => (
                <div key={`f${r}`} style={{ position: "sticky", top: 0, zIndex: 3, height: 0 }}>
                  <div style={{ position: "absolute", top: sorTeteje[r], left: 0, right: 0 }}>
                    {/* Átlátszatlan aljzat a TELJES látható szélességben: a
                        fejléc-cellák csak az oszlopokig érnek, és az utolsó
                        oszloptól jobbra a mögötte elhaladó hónap-elválasztó
                        sáv (pl. "❄️ JANUÁR ❄️") vége átütött a fejléc-zónában. */}
                    <div
                      style={{
                        position: "absolute",
                        left: gorgetes.left,
                        width: meret.szeles,
                        height: sorMagassaga[r],
                      }}
                      className="border-b border-border bg-surface-2"
                    />
                    {[...fagyasztottOszlopok, ...lathatoOszlopok].map((c) => {
                      if (oszlopSzelessege[c] === 0) return null;
                      const cl = cella(r, c);
                      const fagyott = c < fagyasztott;
                      const bal = fagyott ? oszlopBal[c] + gorgetes.left : oszlopBal[c];
                      return (
                        <div
                          key={c}
                          style={{
                            position: "absolute",
                            left: bal,
                            width: oszlopSzelessege[c],
                            height: sorMagassaga[r],
                            zIndex: fagyott ? 2 : 1,
                            // A fejléc-blokkban is látszódjon a cella színe: a
                            // külsős tábla felső sorai a JELMAGYARÁZAT (zöld =
                            // ..., piros = ...), szín nélkül értelmetlenek.
                            ...cellaStilus(cl?.szin),
                          }}
                          onPointerDown={(e) => {
                            // Koppintás a már kijelölt fejléc-cellára =
                            // szerkesztés (lásd a Cella azonos kezelőjét).
                            if (e.pointerType !== "touch" || !canEdit) return;
                            if (kijelolt.sor === r && kijelolt.oszlop === c) {
                              e.preventDefault();
                              setTartomany(null);
                              setSzerkesztes({ pont: { sor: r, oszlop: c }, ertek: cl?.ertek ?? "" });
                            }
                          }}
                          onMouseDown={() => {
                            setKijelolt({ sor: r, oszlop: c });
                            setTartomany(null);
                          }}
                          onDoubleClick={() =>
                            canEdit && setSzerkesztes({ pont: { sor: r, oszlop: c }, ertek: cl?.ertek ?? "" })
                          }
                          className="overflow-hidden border-b border-r border-border bg-surface-2 px-1.5 text-[11.5px] font-medium leading-[24px] text-text-primary"
                          title={cl?.ertek ?? undefined}
                        >
                          {szerkesztes?.pont.sor === r && szerkesztes?.pont.oszlop === c ? (
                            <input
                              autoFocus
                              value={szerkesztes.ertek}
                              onChange={(e) => setSzerkesztes({ ...szerkesztes, ertek: e.target.value })}
                              onBlur={() => {
                                mentesSzoveg(szerkesztes.pont, szerkesztes.ertek);
                                setSzerkesztes(null);
                              }}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") e.currentTarget.blur();
                                if (e.key === "Escape") {
                                  e.stopPropagation();
                                  setSzerkesztes(null);
                                }
                              }}
                              className="h-full w-full bg-surface-1 text-[12px] text-text-primary outline-none"
                            />
                          ) : (
                            <span className="block truncate">{cl?.ertek ?? ""}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}

              {/* BEFAGYASZTOTT OSZLOPOK - valódi CSS `position: sticky`-vel,
                  oszloponként egy-egy nulla méretű "horgony" csomópontban. */}
              {fagyasztottOszlopok.map((c) => (
                <div key={`frz${c}`} style={{ position: "sticky", left: 0, zIndex: 2, width: 0, height: 0 }}>
                  {lathatoSorok.map((r) =>
                    sorTerkep.get(r)?.elvalaszto ? null : <Cella key={r} sor={r} oszlop={c} fagyott />,
                  )}
                </div>
              ))}

              {lathatoSorok.map((r) => {
                const sorAdat = sorTerkep.get(r);
                // A rejtett sor 0 magas - nem rajzolunk belőle semmit.
                if (sorMagassaga[r] === 0) return null;
                // HÓNAP-ELVÁLASZTÓ: nem cellák sora, hanem egy széles,
                // középre írt sáv - az évet egyben görgetve ez mondja meg,
                // hol tartunk.
                if (sorAdat?.elvalaszto) {
                  const felirat =
                    munkalap.oszlopok
                      .map((o) => cella(r, o.idx)?.ertek)
                      .find((e) => e && e.trim()) ?? "";
                  return (
                    <div
                      key={r}
                      style={{
                        position: "absolute",
                        top: sorTeteje[r],
                        left: gorgetes.left,
                        width: meret.szeles,
                        height: sorMagassaga[r],
                        // A rögzített fejléc-sorok (zIndex 3) ALATT kell
                        // maradnia: 3-mal a hónap-felirat görgetéskor a
                        // fejlécre csúszott rá.
                        zIndex: 2,
                      }}
                      onMouseDown={() => {
                        setKijelolt({ sor: r, oszlop: 0 });
                        setTartomany(null);
                      }}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setKijelolt({ sor: r, oszlop: 0 });
                        setMenu({ x: e.clientX, y: e.clientY, pont: { sor: r, oszlop: 0 } });
                      }}
                      className="flex cursor-pointer items-center justify-center border-y border-border bg-bg-accent text-[17px] font-semibold tracking-wide text-text-accent"
                    >
                      {felirat}
                    </div>
                  );
                }
                return (
                  <div key={r}>
                    {lathatoOszlopok.map((c) => (
                      <Cella key={c} sor={r} oszlop={c} fagyott={false} />
                    ))}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* CELLA JOBB GOMBOS MENÜ - másolás/beillesztés, sor/oszlop műveletek. */}
      {menu && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setMenu(null)} onContextMenu={(e) => e.preventDefault()} />
          <div
            style={{ position: "fixed", top: menu.y, left: menu.x, zIndex: 50 }}
            className="min-w-[210px] rounded-[var(--radius)] border border-border bg-surface-1 py-1 shadow-xl"
          >
            {[
              {
                cimke: "Másolás (Ctrl+C)",
                tesz: () => {
                  const masolat = masolatKeszit();
                  if (masolat) {
                    belsoMasolat.current = masolat;
                    void navigator.clipboard?.writeText(masolat.szoveg).catch(() => {});
                  }
                },
              },
              ...(canEdit
                ? [
                    {
                      cimke: "Beillesztés (Ctrl+V)",
                      tesz: () =>
                        void navigator.clipboard
                          ?.readText()
                          .then((szoveg) => beillesztes(szoveg, false))
                          .catch(() =>
                            alert("A vágólap itt nem olvasható - használd a Ctrl+V-t."),
                          ),
                    },
                    {
                      cimke: "Csak értékek beillesztése (Ctrl+Shift+V)",
                      tesz: () =>
                        void navigator.clipboard
                          ?.readText()
                          .then((szoveg) => beillesztes(szoveg, true))
                          .catch(() =>
                            alert("A vágólap itt nem olvasható - használd a Ctrl+Shift+V-t."),
                          ),
                    },
                    { cimke: "Tartalom törlése (Delete)", tesz: () => tartalmatTorol() },
                    { elvalaszto: true } as const,
                    { cimke: "Sor beszúrása fölé", tesz: () => hivas("/sor", { method: "POST", body: JSON.stringify({ idx: menu.pont.sor }) }) },
                    { cimke: "Sor beszúrása alá", tesz: () => hivas("/sor", { method: "POST", body: JSON.stringify({ idx: menu.pont.sor, ala: true }) }) },
                    { cimke: "Oszlop beszúrása balra", tesz: () => hivas("/oszlop", { method: "POST", body: JSON.stringify({ idx: menu.pont.oszlop }) }) },
                    { cimke: "Oszlop beszúrása jobbra", tesz: () => hivas("/oszlop", { method: "POST", body: JSON.stringify({ idx: menu.pont.oszlop, ala: true }) }) },
                  ]
                : []),
              // Saját elrejtés: bárki a saját nézetében - adat nem vész el,
              // más nem lát belőle semmit.
              ...(menu.pont.oszlop >= fagyasztott && oszlopTerkep.get(menu.pont.oszlop)
                ? [
                    {
                      cimke: `${oszlopBetu(menu.pont.oszlop)} oszlop elrejtése (saját nézet)`,
                      tesz: () => {
                        const o = oszlopTerkep.get(menu.pont.oszlop);
                        if (o) sajatRejtes([o.id], true);
                      },
                    },
                  ]
                : []),
              // Globális elrejtés: admin-vezérlő, mindenki elől takar.
              ...(rejtettetLatja && canEdit && menu.pont.oszlop >= fagyasztott
                ? [
                    {
                      cimke: `${oszlopBetu(menu.pont.oszlop)} oszlop elrejtése mindenkinél`,
                      tesz: () =>
                        hivas(`/oszlop/${menu.pont.oszlop}`, {
                          method: "PUT",
                          body: JSON.stringify({ rejtett: true }),
                        }),
                    },
                  ]
                : []),
              ...(rejtettetLatja && canEdit && menu.pont.sor >= munkalap.fejlec_sorok
                ? [
                    {
                      cimke: `${menu.pont.sor + 1}. sor elrejtése mindenkinél`,
                      tesz: () =>
                        hivas(`/sor/${menu.pont.sor}`, {
                          method: "PUT",
                          body: JSON.stringify({ rejtett: true }),
                        }),
                    },
                  ]
                : []),
            ].map((elem, i) =>
              "elvalaszto" in elem ? (
                <div key={`e${i}`} className="my-1 h-px bg-border" />
              ) : (
                <button
                  key={elem.cimke}
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    elem.tesz();
                    setMenu(null);
                  }}
                  className="block w-full px-3 py-1.5 text-left text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
                >
                  {elem.cimke}
                </button>
              ),
            )}
            {canDelete && (
              <>
                <div className="my-1 h-px bg-border" />
                {[
                  { cimke: `${menu.pont.sor + 1}. sor törlése`, ut: `/sor/${menu.pont.sor}` },
                  { cimke: `${oszlopBetu(menu.pont.oszlop)} oszlop törlése`, ut: `/oszlop/${menu.pont.oszlop}` },
                ].map((elem) => (
                  <button
                    key={elem.cimke}
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      if (confirm(`${elem.cimke}? A tartalma is elveszik.`)) hivas(elem.ut, { method: "DELETE" });
                      setMenu(null);
                    }}
                    className="block w-full px-3 py-1.5 text-left text-[12.5px] text-text-danger hover:bg-surface-3 disabled:opacity-40"
                  >
                    {elem.cimke}
                  </button>
                ))}
              </>
            )}
          </div>
        </>
      )}

      {/* OSZLOPFEJLÉC JOBB GOMBOS MENÜ - elrejtés (akár többet egyszerre),
          szélesség, beszúrás, törlés. */}
      {fejlecMenu &&
        (() => {
          const celok = fejlecMenuOszlopai(fejlecMenu.oszlop);
          const celIdk = celok
            .map((c) => oszlopTerkep.get(c)?.id)
            .filter((id): id is number => id !== undefined);
          return (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setFejlecMenu(null)}
                onContextMenu={(e) => e.preventDefault()}
              />
              <div
                style={{ position: "fixed", top: fejlecMenu.y, left: fejlecMenu.x, zIndex: 50 }}
                className="min-w-[230px] rounded-[var(--radius)] border border-border bg-surface-1 py-1 shadow-xl"
              >
                {celIdk.length > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      sajatRejtes(celIdk, true);
                      setFejlecMenu(null);
                    }}
                    className="block w-full px-3 py-1.5 text-left text-[12.5px] text-text-secondary hover:bg-surface-3"
                  >
                    {celok.length > 1
                      ? `${celok.length} oszlop elrejtése (saját nézet)`
                      : `${oszlopBetu(celok[0])} oszlop elrejtése (saját nézet)`}
                  </button>
                )}
                {rejtettetLatja && canEdit && celok.length > 0 && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={async () => {
                      setFejlecMenu(null);
                      for (const c of celok) {
                        // Sorban, nem párhuzamosan: az elrejtés nem indexel át,
                        // de a hivas() frissíti a munkalapot.
                        await hivas(`/oszlop/${c}`, { method: "PUT", body: JSON.stringify({ rejtett: true }) });
                      }
                    }}
                    className="block w-full px-3 py-1.5 text-left text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
                  >
                    {celok.length > 1
                      ? `${celok.length} oszlop elrejtése mindenkinél`
                      : `${oszlopBetu(celok[0])} oszlop elrejtése mindenkinél`}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    tartalomhozIgazit(fejlecMenu.oszlop);
                    setFejlecMenu(null);
                  }}
                  className="block w-full px-3 py-1.5 text-left text-[12.5px] text-text-secondary hover:bg-surface-3"
                >
                  Szélesség igazítása a tartalomhoz
                </button>
                {canEdit && (
                  <>
                    <div className="my-1 h-px bg-border" />
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        void hivas("/oszlop", { method: "POST", body: JSON.stringify({ idx: fejlecMenu.oszlop }) });
                        setFejlecMenu(null);
                      }}
                      className="block w-full px-3 py-1.5 text-left text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
                    >
                      Oszlop beszúrása balra
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        void hivas("/oszlop", {
                          method: "POST",
                          body: JSON.stringify({ idx: fejlecMenu.oszlop, ala: true }),
                        });
                        setFejlecMenu(null);
                      }}
                      className="block w-full px-3 py-1.5 text-left text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
                    >
                      Oszlop beszúrása jobbra
                    </button>
                  </>
                )}
                {canDelete && (
                  <>
                    <div className="my-1 h-px bg-border" />
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        if (confirm(`${oszlopBetu(fejlecMenu.oszlop)} oszlop törlése? A tartalma is elveszik.`))
                          void hivas(`/oszlop/${fejlecMenu.oszlop}`, { method: "DELETE" });
                        setFejlecMenu(null);
                      }}
                      className="block w-full px-3 py-1.5 text-left text-[12.5px] text-text-danger hover:bg-surface-3 disabled:opacity-40"
                    >
                      {oszlopBetu(fejlecMenu.oszlop)} oszlop törlése
                    </button>
                  </>
                )}
              </div>
            </>
          );
        })()}

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-text-muted">
        {DISZPO_SZINEK.map((szin) => (
          <span key={szin} className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: SZIN_LEIRAS[szin].hatter }} />
            {SZIN_LEIRAS[szin].jelentes}
          </span>
        ))}
        <span className="ml-auto">
          Nyilak: mozgás · gépelés, Enter vagy F2: szerkesztés · Ctrl+Z/Y: visszavonás/újra · Ctrl+C/V: másolás
          (színnel) / beillesztés · Ctrl+Shift+V: csak értékek · Shift+nyíl vagy húzás: tartomány · Delete: tartalom
          törlése · jobb gomb: menü (cella és oszlopfejléc)
        </span>
      </div>
    </div>
  );
}
