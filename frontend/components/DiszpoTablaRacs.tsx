"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
// CSAK TÍPUS a lib/api-ból: az érték szerinti import behúzná a `next/headers`-t
// (a modul szerver oldalon süti-alapú hitelesítéssel hív), ami
// klienskomponensben build-hibát okoz. A színek ezért a kliens-biztos
// lib/diszpoSzin-ből jönnek - ugyanaz a szétválasztás, mint a lib/utokovetes-nél.
import type { DiszpoMunkalap } from "@/lib/api";
import { DISZPO_SZINEK, SZIN_LEIRAS, type DiszpoSzin } from "@/lib/diszpoSzin";

// A rács MÉRETEI. Fixek, mert a virtualizálás ebből számol: enélkül minden
// görgetésnél meg kellene mérni a tényleges cellamagasságokat.
const SOR_MAGASSAG = 26;
//: A HÓNAP-ELVÁLASZTÓ sor magasabb és középre írt: az évet egyben görgetve
//: ez az egyetlen fogódzó, hol tart az ember. A Sheetben is kiugrik.
const ELVALASZTO_MAGASSAG = 46;
const OSZLOP_SZELES = 116;
const SORFEJ_SZELES = 46;
const OSZLOPFEJ_MAGAS = 24;
//: Ennyi sorral/oszloppal többet rajzolunk a látható ablakon kívül, hogy
//: görgetéskor ne villanjon be üres terület.
const RATARTAS = 6;

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

type Pont = { sor: number; oszlop: number };
type Tartomany = { tol: Pont; ig: Pont };

function normalizal(t: Tartomany) {
  return {
    sor1: Math.min(t.tol.sor, t.ig.sor),
    sor2: Math.max(t.tol.sor, t.ig.sor),
    oszlop1: Math.min(t.tol.oszlop, t.ig.oszlop),
    oszlop2: Math.max(t.tol.oszlop, t.ig.oszlop),
  };
}

/** A HYPE 2026 táblázat egy munkalapja - TÁBLÁZATKÉNT, nem listaként.
 *
 * Úgy kell viselkednie, mint a Google Sheets, mert a munka is ugyanaz: sorok
 * és oszlopok, kijelölés, gépelés, színezés. Ezért van benne sorszám és
 * oszlopbetű, fagyasztott fejléc, billentyűs mozgás, tartomány-kijelölés, és
 * sor/oszlop beszúrás.
 *
 * A CELLA SZÍNE ITT ADAT: abból számoljuk, ki hány napot dolgozott (lásd
 * backend services/munkanap_szamlalo.py).
 *
 * MIÉRT VIRTUALIZÁLT? Mert az egész év egyben látszik (a külsős munkalap 381
 * sor x 146 oszlop = 55 ezer cella), és ennyi DOM-elemtől a böngésző megáll.
 * Csak a látható ablakot rajzoljuk ki; a görgetősáv a teljes méretet mutatja,
 * tehát a görgetés ugyanaz, mintha minden ott volna. */
export function DiszpoTablaRacs({
  munkalap,
  canEdit = true,
  canDelete = false,
  emberek,
}: {
  munkalap: DiszpoMunkalap;
  canEdit?: boolean;
  canDelete?: boolean;
  /** A munkatársak az oszlop-ember kötéshez. */
  emberek: { id: number; nev: string }[];
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
  const [busy, setBusy] = useState(false);
  // A legutóbbi Ctrl+C belső másolata: a szöveg mellett a cellák SZÍNÉT is
  // őrzi. A rendszer-vágólapra csak szöveg fér; beillesztéskor a szöveg
  // egyezéséből ismerjük fel, hogy a sajátunkat illesztik vissza - olyankor
  // a szín is megy (a felhasználó kérése).
  const belsoMasolat = useRef<{ szoveg: string; racs: { ertek: string | null; szin: string | null }[][] } | null>(null);

  const sorSzam = Math.max(munkalap.sor_szam, munkalap.sorok.length);
  const oszlopSzam = munkalap.oszlop_szam;

  const oszlopTerkep = useMemo(() => new Map(munkalap.oszlopok.map((o) => [o.idx, o])), [munkalap.oszlopok]);

  // Az oszlopok BALJA és SZÉLESSÉGE - halmozva, mint a soroknál: a REJTETT
  // oszlop 0 széles, így a többi magától összecsúszik (a felhasználó kérése:
  // a már nem kellő oszlopok eltüntethetők az adatuk elvesztése nélkül).
  const { oszlopBal, oszlopSzelessege } = useMemo(() => {
    const bal: number[] = new Array(oszlopSzam + 1);
    const szel: number[] = new Array(oszlopSzam);
    let fut = 0;
    for (let c = 0; c < oszlopSzam; c++) {
      bal[c] = fut;
      szel[c] = oszlopTerkep.get(c)?.rejtett ? 0 : OSZLOP_SZELES;
      fut += szel[c];
    }
    bal[oszlopSzam] = fut;
    return { oszlopBal: bal, oszlopSzelessege: szel };
  }, [oszlopTerkep, oszlopSzam]);

  const rejtettOszlopok = useMemo(
    () => munkalap.oszlopok.filter((o) => o.rejtett).sort((a, b) => a.idx - b.idx),
    [munkalap.oszlopok],
  );

  // A sorok TETEJE és MAGASSÁGA - halmozva. Azért kell tömb, mert az
  // elválasztó sorok magasabbak: fix magassággal a pozíciók elcsúsznának.
  // A REJTETT sor 0 magas (mint a rejtett oszlop 0 széles) - a többi sor
  // magától összecsúszik, az adat pedig megmarad (a felhasználó kérése).
  const { sorTeteje, sorMagassaga, teljesMagassag } = useMemo(() => {
    const elvalasztoSorok = new Set(munkalap.sorok.filter((s) => s.elvalaszto).map((s) => s.idx));
    const rejtettSorIdxek = new Set(munkalap.sorok.filter((s) => s.rejtett).map((s) => s.idx));
    const teteje: number[] = new Array(sorSzam + 1);
    const magassaga: number[] = new Array(sorSzam);
    let fut = 0;
    for (let r = 0; r < sorSzam; r++) {
      teteje[r] = fut;
      magassaga[r] = rejtettSorIdxek.has(r) ? 0 : elvalasztoSorok.has(r) ? ELVALASZTO_MAGASSAG : SOR_MAGASSAG;
      fut += magassaga[r];
    }
    teteje[sorSzam] = fut;
    return { sorTeteje: teteje, sorMagassaga: magassaga, teljesMagassag: fut };
  }, [munkalap.sorok, sorSzam]);

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

  // Az első oszlopok BEFAGYASZTVA: 146 oszlopnál a dátum nélkül nem lehet
  // tudni, melyik sorban vagyunk. Ahol nincs dátum-oszlop, ott egy elég.
  // TELEFONON (keskeny nézetben) viszont csak EGY oszlop marad rögzítve: a
  // három rögzített oszlop (3 x 116px) egy ~390px-es kijelzőt teljesen
  // kitöltene, és a görgethető rész el sem férne mellettük (a felhasználó
  // jelzése). A mérés a rács saját szélességén történik (lásd a
  // ResizeObserver-t lentebb), nem a viewporton - így a szűk oldalsávos
  // elrendezésekben is jól dönt.
  const keskeny = meret.szeles < 640;
  const fagyasztott = !keskeny && munkalap.sorok.some((s) => s.datum) ? 3 : 1;
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

  const cellaTerkep = useMemo(() => {
    const t = new Map<number, { ertek: string | null; szin: string | null }>();
    for (const [sor, oszlop, ertek, szin] of munkalap.cellak) {
      t.set(sor * 10000 + oszlop, { ertek, szin });
    }
    return t;
  }, [munkalap.cellak]);

  const cella = useCallback(
    (sor: number, oszlop: number) => cellaTerkep.get(sor * 10000 + oszlop),
    [cellaTerkep],
  );

  const sorTerkep = useMemo(() => new Map(munkalap.sorok.map((s) => [s.idx, s])), [munkalap.sorok]);

  useEffect(() => {
    const elem = gorgetoRef.current;
    if (!elem) return;
    const merj = () => setMeret({ szeles: elem.clientWidth, magas: elem.clientHeight });
    merj();
    const figyelo = new ResizeObserver(merj);
    figyelo.observe(elem);
    return () => figyelo.disconnect();
  }, []);

  // A LÁTHATÓ ABLAK: csak ezt rajzoljuk ki.
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

  async function hivas(utvonal: string, opciok: RequestInit): Promise<boolean> {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/diszpo-tabla/${munkalap.id}${utvonal}`, opciok);
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return false;
      }
      router.refresh();
      return true;
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  const kijeloltCellak = useCallback((): Pont[] => {
    if (!tartomany) return [kijelolt];
    const { sor1, sor2, oszlop1, oszlop2 } = normalizal(tartomany);
    const pontok: Pont[] = [];
    for (let r = sor1; r <= sor2; r++) for (let c = oszlop1; c <= oszlop2; c++) pontok.push({ sor: r, oszlop: c });
    return pontok;
  }, [tartomany, kijelolt]);

  /** Színezés/törlés a teljes kijelölésre - egy kör-úttal. */
  function szinez(szin: DiszpoSzin | null) {
    const pontok = kijeloltCellak();
    hivas("/cellak", {
      method: "PUT",
      body: JSON.stringify({
        cellak: pontok.map((p) => ({ sor_idx: p.sor, oszlop_idx: p.oszlop, szin, szin_valtozik: true })),
      }),
    });
  }

  function tartalmatTorol() {
    const pontok = kijeloltCellak();
    hivas("/cellak", {
      method: "PUT",
      body: JSON.stringify({
        cellak: pontok.map((p) => ({ sor_idx: p.sor, oszlop_idx: p.oszlop, ertek: null, ertek_valtozik: true })),
      }),
    });
  }

  function mentesSzoveg(pont: Pont, ertek: string) {
    hivas("/cella", {
      method: "PUT",
      body: JSON.stringify({ sor_idx: pont.sor, oszlop_idx: pont.oszlop, ertek, ertek_valtozik: true }),
    });
  }

  const lepj = useCallback(
    (dSor: number, dOszlop: number, kiterjeszt = false) => {
      // Vízszintes lépésnél a REJTETT oszlopokat átugorjuk - különben a
      // kijelölés egy láthatatlan cellán állna meg.
      let celOszlop = Math.min(Math.max(kijelolt.oszlop + dOszlop, 0), oszlopSzam - 1);
      if (dOszlop !== 0) {
        const irany = dOszlop > 0 ? 1 : -1;
        while (celOszlop >= 0 && celOszlop < oszlopSzam && oszlopTerkep.get(celOszlop)?.rejtett) {
          celOszlop += irany;
        }
        if (celOszlop < 0 || celOszlop >= oszlopSzam) celOszlop = kijelolt.oszlop;
      }
      // Függőleges lépésnél a REJTETT sorokat is átugorjuk - ugyanaz az elv,
      // mint a rejtett oszlopoknál.
      let celSor = Math.min(Math.max(kijelolt.sor + dSor, munkalap.fejlec_sorok), sorSzam - 1);
      if (dSor !== 0) {
        const sorIrany = dSor > 0 ? 1 : -1;
        while (celSor >= munkalap.fejlec_sorok && celSor < sorSzam && sorTerkep.get(celSor)?.rejtett) {
          celSor += sorIrany;
        }
        if (celSor < munkalap.fejlec_sorok || celSor >= sorSzam) celSor = kijelolt.sor;
      }
      const uj = {
        sor: celSor,
        oszlop: celOszlop,
      };
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
    [kijelolt, tartomany, sorSzam, oszlopSzam, munkalap.fejlec_sorok, fagyasztott, fagyasztottSzeles, oszlopBal, oszlopSzelessege, oszlopTerkep, sorTerkep, sorTeteje, sorMagassaga],
  );

  // BILLENTYŰZET: ahogy a táblázatban. Nyilak, Enter, Tab, gépelés, Delete.
  useEffect(() => {
    function kezel(e: KeyboardEvent) {
      if (szerkesztes || !canEdit) return;
      const cel = e.target as HTMLElement | null;
      if (cel && (cel.tagName === "INPUT" || cel.tagName === "TEXTAREA" || cel.isContentEditable)) return;
      if (menu) setMenu(null);

      if (e.key === "ArrowDown") return void (e.preventDefault(), lepj(1, 0, e.shiftKey));
      if (e.key === "ArrowUp") return void (e.preventDefault(), lepj(-1, 0, e.shiftKey));
      if (e.key === "ArrowLeft") return void (e.preventDefault(), lepj(0, -1, e.shiftKey));
      if (e.key === "ArrowRight") return void (e.preventDefault(), lepj(0, 1, e.shiftKey));
      if (e.key === "Tab") return void (e.preventDefault(), lepj(0, e.shiftKey ? -1 : 1));
      if (e.key === "Enter") {
        e.preventDefault();
        setSzerkesztes({ pont: kijelolt, ertek: cella(kijelolt.sor, kijelolt.oszlop)?.ertek ?? "" });
        return;
      }
      if (e.key === "Delete" || e.key === "Backspace") return void (e.preventDefault(), tartalmatTorol());
      if (e.key === "Escape") return void setTartomany(null);
      // Gépelés: azonnal szerkesztés, a leütött karakterrel - mint a Sheetsben.
      if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        setSzerkesztes({ pont: kijelolt, ertek: e.key });
      }
    }
    window.addEventListener("keydown", kezel);
    return () => window.removeEventListener("keydown", kezel);
  });

  // MÁSOLÁS (Ctrl+C) - a felhasználó kérése: a kijelölt cella/tartomány
  // szövege a rendszer-vágólapra kerül (Sheets-be is beilleszthető), a SZÍNE
  // pedig egy belső pufferbe. A beillesztés (lent) felismeri a saját
  // másolatot, és olyankor a színt is visszateszi, nem csak a szöveget.
  useEffect(() => {
    function masol(e: ClipboardEvent) {
      if (szerkesztes) return;
      const cel = e.target as HTMLElement | null;
      if (cel && (cel.tagName === "INPUT" || cel.tagName === "TEXTAREA" || cel.isContentEditable)) return;
      const tolS = Math.min(tartomany?.tol.sor ?? kijelolt.sor, tartomany?.ig.sor ?? kijelolt.sor);
      const igS = Math.max(tartomany?.tol.sor ?? kijelolt.sor, tartomany?.ig.sor ?? kijelolt.sor);
      const tolO = Math.min(tartomany?.tol.oszlop ?? kijelolt.oszlop, tartomany?.ig.oszlop ?? kijelolt.oszlop);
      const igO = Math.max(tartomany?.tol.oszlop ?? kijelolt.oszlop, tartomany?.ig.oszlop ?? kijelolt.oszlop);
      // Csak a LÁTHATÓ sorok/oszlopok - ugyanígy hagyja ki őket a beillesztés is.
      const sorIdxek: number[] = [];
      for (let r = tolS; r <= igS; r++) if (!sorTerkep.get(r)?.rejtett) sorIdxek.push(r);
      const oszlopIdxek: number[] = [];
      for (let c = tolO; c <= igO; c++) if (!oszlopTerkep.get(c)?.rejtett) oszlopIdxek.push(c);
      if (sorIdxek.length === 0 || oszlopIdxek.length === 0) return;
      const racs = sorIdxek.map((r) =>
        oszlopIdxek.map((c) => {
          const cl = cella(r, c);
          return { ertek: cl?.ertek ?? null, szin: cl?.szin ?? null };
        }),
      );
      const szoveg = racs.map((sor) => sor.map((x) => x.ertek ?? "").join("\t")).join("\n");
      e.clipboardData?.setData("text/plain", szoveg);
      e.preventDefault();
      belsoMasolat.current = { szoveg, racs };
    }
    window.addEventListener("copy", masol);
    return () => window.removeEventListener("copy", masol);
  });

  // BEILLESZTÉS a vágólapról (Ctrl+V) - a felhasználó kérése. Egyetlen érték
  // a kijelölt cellába megy; táblázatból másolt tartomány (tab/sortörés
  // tagolás, ahogy a Sheets/Excel adja) cellánként szétosztva, a kijelölttől
  // jobbra-lefelé. A REJTETT oszlopokat kihagyjuk, ahogy a Sheets is teszi.
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
      const normalizalt = szoveg.replace(/\r/g, "").replace(/\n$/, "");
      const sorok = normalizalt.split("\n").map((sor) => sor.split("\t"));
      // Ha a vágólapon a SAJÁT másolatunk van (Ctrl+C ebből a táblából), a
      // színt is visszatesszük - máshonnan (Sheets, Excel) jött szövegnél
      // csak a tartalom megy, ott nincs honnan tudni a színt.
      const belso = belsoMasolat.current;
      const szines = belso !== null && belso.szoveg === normalizalt ? belso : null;
      // A cél-oszlopok: a kijelölttől jobbra lévő LÁTHATÓ oszlopok sorban.
      const celOszlopok: number[] = [];
      for (let c = kijelolt.oszlop; c < oszlopSzam; c++) {
        if (!oszlopTerkep.get(c)?.rejtett) celOszlopok.push(c);
      }
      // A cél-sorok is a LÁTHATÓAK: a rejtett sorokat a beillesztés is
      // kihagyja, ahogy a rejtett oszlopokat (és ahogy a Sheets teszi).
      const celSorok: number[] = [];
      for (let r = kijelolt.sor; r < sorSzam; r++) {
        if (!sorTerkep.get(r)?.rejtett) celSorok.push(r);
      }
      const cellak: {
        sor_idx: number;
        oszlop_idx: number;
        ertek: string | null;
        ertek_valtozik: boolean;
        szin?: string | null;
        szin_valtozik?: boolean;
      }[] = [];
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
            ...(szines
              ? { szin: szines.racs[dr]?.[dc]?.szin ?? null, szin_valtozik: true }
              : {}),
          });
        });
      });
      if (cellak.length > 0) {
        hivas("/cellak", { method: "PUT", body: JSON.stringify({ cellak }) });
      }
    }
    window.addEventListener("paste", beilleszt);
    return () => window.removeEventListener("paste", beilleszt);
  });

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
        } ${kijeloltE(sor, oszlop) ? "outline outline-2 -outline-offset-2 outline-text-accent" : ""} ${
          // A fagyasztott oszlopnak MINDIG kell átlátszatlan háttér, különben
          // görgetéskor a mögötte (a rács tartalmában) elhaladó, színes sorok
          // átütnének rajta. Az "üresen hagyva" jelölés (feher) szándékosan
          // nem fest hátteret (lásd cellaStilus) - itt ezért külön kezeljük.
          fagyott && (!c?.szin || uresJelolt) ? "bg-surface-2" : ""
        }`}
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
          setKijelolt({ sor, oszlop });
          setMenu({ x: e.clientX, y: e.clientY, pont: { sor, oszlop } });
        }}
        title={c?.ertek ?? undefined}
      >
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
              if (e.key === "Escape") setSzerkesztes(null);
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

  return (
    <div className="space-y-2" onMouseUp={() => setHuzas(false)}>
      {/* ESZKÖZTÁR: színezés + sor/oszlop műveletek. */}
      <div className="flex flex-wrap items-center gap-1.5">
        {canEdit && (
          <>
            {DISZPO_SZINEK.map((szin) => (
              <button
                key={szin}
                type="button"
                disabled={busy}
                title={SZIN_LEIRAS[szin].jelentes}
                onClick={() => szinez(szin)}
                style={{ backgroundColor: SZIN_LEIRAS[szin].hatter, color: SZIN_LEIRAS[szin].szoveg }}
                className="rounded-[var(--radius)] px-2.5 py-1 text-[12px] font-medium disabled:opacity-40"
              >
                {SZIN_LEIRAS[szin].cimke}
              </button>
            ))}
            <button
              type="button"
              disabled={busy}
              onClick={() => szinez(null)}
              className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
            >
              Szín törlése
            </button>
            <span className="mx-1 h-4 w-px bg-border" />
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
              + Oszlop jobbra
            </button>
            {/* KÜLÖN GOMB az oszlop elrejtésére (a felhasználó kérése) - eddig
                csak a jobb-klikk menüből ment. A kijelölt oszlopo(ka)t rejti:
                tartomány-kijelölésnél az összes érintett, nem-fagyasztott
                oszlopot. A fagyasztott (dátum/nap/diszpószám) oszlopok
                maradnak: azok igazítanak el, melyik sorban vagyunk. */}
            {(() => {
              const tol = Math.min(tartomany?.tol.oszlop ?? kijelolt.oszlop, tartomany?.ig.oszlop ?? kijelolt.oszlop);
              const ig = Math.max(tartomany?.tol.oszlop ?? kijelolt.oszlop, tartomany?.ig.oszlop ?? kijelolt.oszlop);
              const rejtendok: number[] = [];
              for (let c = Math.max(tol, fagyasztott); c <= ig; c++) {
                if (!oszlopTerkep.get(c)?.rejtett) rejtendok.push(c);
              }
              if (rejtendok.length === 0) return null;
              return (
                <button
                  type="button"
                  disabled={busy}
                  title="A kijelölt oszlop(ok) elrejtése - lent a Rejtett oszlopok sávból bármikor visszahozható"
                  onClick={async () => {
                    for (const c of rejtendok) {
                      // Sorban, nem párhuzamosan: a hivas() frissíti a munkalapot,
                      // és az oszlop-indexek stabilak (az elrejtés nem indexel át).
                      await hivas(`/oszlop/${c}`, { method: "PUT", body: JSON.stringify({ rejtett: true }) });
                    }
                  }}
                  className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
                >
                  {rejtendok.length > 1
                    ? `${rejtendok.length} oszlop elrejtése`
                    : `${oszlopBetu(rejtendok[0])} oszlop elrejtése`}
                </button>
              );
            })()}
            {/* UGYANEZ SOROKRA (a felhasználó kérése): a kijelölt sor(ok)
                elrejtése - a fejléc-sorok maradnak, azok igazítanak el. */}
            {(() => {
              const tol = Math.min(tartomany?.tol.sor ?? kijelolt.sor, tartomany?.ig.sor ?? kijelolt.sor);
              const ig = Math.max(tartomany?.tol.sor ?? kijelolt.sor, tartomany?.ig.sor ?? kijelolt.sor);
              const rejtendok: number[] = [];
              for (let r = Math.max(tol, munkalap.fejlec_sorok); r <= ig; r++) {
                if (!sorTerkep.get(r)?.rejtett) rejtendok.push(r);
              }
              if (rejtendok.length === 0) return null;
              return (
                <button
                  type="button"
                  disabled={busy}
                  title="A kijelölt sor(ok) elrejtése - lent a Rejtett sorok sávból bármikor visszahozható"
                  onClick={async () => {
                    for (const r of rejtendok) {
                      // Sorban, nem párhuzamosan - mint az oszlopoknál.
                      await hivas(`/sor/${r}`, { method: "PUT", body: JSON.stringify({ rejtett: true }) });
                    }
                  }}
                  className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
                >
                  {rejtendok.length > 1 ? `${rejtendok.length} sor elrejtése` : `${rejtendok[0] + 1}. sor elrejtése`}
                </button>
              );
            })()}
          </>
        )}
        <span className="ml-auto text-[11.5px] text-text-muted">
          {oszlopBetu(kijelolt.oszlop)}
          {kijelolt.sor + 1}
          {kijeloltOszlop?.cimke ? ` · ${kijeloltOszlop.cimke}` : ""}
          {kijeloltSor?.datum ? ` · ${kijeloltSor.datum}` : ""}
          {tartomany ? ` · ${kijeloltCellak().length} cella` : ""}
        </span>
      </div>

      {/* A REJTETT oszlopok visszahozása: felsoroljuk őket, egy kattintás
          újra megjeleníti. Enélkül az elrejtés egyirányú út lenne. */}
      {rejtettOszlopok.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[12px]">
          <span className="text-text-secondary">Rejtett oszlopok ({rejtettOszlopok.length}):</span>
          {rejtettOszlopok.map((o) => (
            <button
              key={o.idx}
              type="button"
              disabled={busy || !canEdit}
              title="Oszlop megjelenítése"
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

      {/* A REJTETT sorok visszahozása - ugyanaz, mint az oszlopoknál. */}
      {rejtettSorok.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[12px]">
          <span className="text-text-secondary">Rejtett sorok ({rejtettSorok.length}):</span>
          {rejtettSorok.map((s) => (
            <button
              key={s.idx}
              type="button"
              disabled={busy || !canEdit}
              title="Sor megjelenítése"
              onClick={() => hivas(`/sor/${s.idx}`, { method: "PUT", body: JSON.stringify({ rejtett: false }) })}
              className="rounded-[var(--radius)] border border-border px-2 py-0.5 text-text-secondary hover:bg-surface-2 disabled:opacity-40"
            >
              {s.idx + 1}.{s.datum ? ` · ${s.datum}` : ""} ×
            </button>
          ))}
        </div>
      )}

      {/* Az oszlop-ember kötés: enélkül az oszlop színei nem számítanak bele a
          munkanap-számlálásba (lásd backend routes/diszpo_tabla.py). */}
      {canEdit && munkalap.fejlec_sorok > 1 && kijeloltOszlop && (
        <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-1.5 text-[12.5px]">
          <span className="text-text-secondary">
            „{kijeloltOszlop.cimke ?? oszlopBetu(kijelolt.oszlop)}” oszlop munkatársa:
          </span>
          <select
            value={kijeloltOszlop.employee_id ?? ""}
            disabled={busy}
            onChange={(e) =>
              hivas(`/oszlop/${kijelolt.oszlop}`, {
                method: "PUT",
                body: JSON.stringify({ employee_id: e.target.value ? Number(e.target.value) : null }),
              })
            }
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[12.5px] text-text-primary"
          >
            <option value="">– nincs hozzákötve –</option>
            {emberek.map((emb) => (
              <option key={emb.id} value={emb.id}>
                {emb.nev}
              </option>
            ))}
          </select>
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
        {/* OSZLOPFEJLÉC (A, B, C…) - a görgetéssel együtt mozog vízszintesen. */}
        <div
          className="relative overflow-hidden border-b border-border bg-surface-3"
          style={{ height: OSZLOPFEJ_MAGAS, marginLeft: SORFEJ_SZELES }}
        >
          {[...fagyasztottOszlopok, ...lathatoOszlopok].map((c) => {
            if (oszlopSzelessege[c] === 0) return null;
            const fagyott = c < fagyasztott;
            const bal = fagyott ? oszlopBal[c] + gorgetes.left : oszlopBal[c];
            return (
              <div
                key={c}
                style={{ position: "absolute", left: bal - gorgetes.left, width: oszlopSzelessege[c], zIndex: fagyott ? 2 : 1 }}
                onClick={() => setTartomany({ tol: { sor: munkalap.fejlec_sorok, oszlop: c }, ig: { sor: sorSzam - 1, oszlop: c } })}
                className={`h-[${OSZLOPFEJ_MAGAS}px] cursor-pointer border-r border-border bg-surface-3 text-center text-[10.5px] leading-[24px] ${
                  kijelolt.oszlop === c ? "text-text-accent" : "text-text-muted"
                }`}
              >
                {oszlopBetu(c)}
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
            {[...fejlecSorok, ...lathatoSorok].map((r) => (
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
            ))}
          </div>

          <div
            ref={gorgetoRef}
            onScroll={(e) =>
              setGorgetes({ top: e.currentTarget.scrollTop, left: e.currentTarget.scrollLeft })
            }
            onContextMenu={(e) => e.preventDefault()}
            className="relative flex-1 overflow-auto"
            style={{ height: "68vh" }}
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
                                if (e.key === "Escape") setSzerkesztes(null);
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
                  oszloponként egy-egy nulla méretű "horgony" csomópontban
                  (ugyanaz a trükk, mint a fenti fejléc-soroké, csak
                  vízszintesen). A böngésző natívan tartja a helyükön
                  görgetéskor, ezért nincs a korábbi kézi
                  `gorgetes.left`-újraszámolásból adódó egy-képkockás
                  késés (ami a villogást/ugrálást okozta), és a cellák
                  mindig átlátszatlan hátteret kapnak (lásd Cella), ezért a
                  mögöttük elhaladó sorok színe sem üt át rajtuk. */}
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
                        // fejlécre csúszott rá. A fagyasztott oszlopokat
                        // (zIndex 2) a DOM-sorrend miatt így is fedi.
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

      {/* JOBB GOMBOS MENÜ - sor/oszlop beszúrás és törlés. */}
      {menu && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setMenu(null)} onContextMenu={(e) => e.preventDefault()} />
          <div
            style={{ position: "fixed", top: menu.y, left: menu.x, zIndex: 50 }}
            className="min-w-[190px] rounded-[var(--radius)] border border-border bg-surface-1 py-1 shadow-xl"
          >
            {[
              { cimke: "Sor beszúrása fölé", tesz: () => hivas("/sor", { method: "POST", body: JSON.stringify({ idx: menu.pont.sor }) }) },
              { cimke: "Sor beszúrása alá", tesz: () => hivas("/sor", { method: "POST", body: JSON.stringify({ idx: menu.pont.sor, ala: true }) }) },
              { cimke: "Oszlop beszúrása balra", tesz: () => hivas("/oszlop", { method: "POST", body: JSON.stringify({ idx: menu.pont.oszlop }) }) },
              { cimke: "Oszlop beszúrása jobbra", tesz: () => hivas("/oszlop", { method: "POST", body: JSON.stringify({ idx: menu.pont.oszlop, ala: true }) }) },
              { cimke: "Tartalom törlése", tesz: () => tartalmatTorol() },
              // A fagyasztott (dátum/nap/diszpószám) oszlopokat nem engedjük
              // elrejteni: azok igazítanak el, melyik sorban vagyunk.
              ...(menu.pont.oszlop >= fagyasztott
                ? [
                    {
                      cimke: `${oszlopBetu(menu.pont.oszlop)} oszlop elrejtése`,
                      tesz: () =>
                        hivas(`/oszlop/${menu.pont.oszlop}`, {
                          method: "PUT",
                          body: JSON.stringify({ rejtett: true }),
                        }),
                    },
                  ]
                : []),
              // A fejléc-sorokat nem engedjük elrejteni - azok a jelmagyarázat.
              ...(menu.pont.sor >= munkalap.fejlec_sorok
                ? [
                    {
                      cimke: `${menu.pont.sor + 1}. sor elrejtése`,
                      tesz: () =>
                        hivas(`/sor/${menu.pont.sor}`, {
                          method: "PUT",
                          body: JSON.stringify({ rejtett: true }),
                        }),
                    },
                  ]
                : []),
            ].map((elem) => (
              <button
                key={elem.cimke}
                type="button"
                disabled={busy || !canEdit}
                onClick={() => {
                  elem.tesz();
                  setMenu(null);
                }}
                className="block w-full px-3 py-1.5 text-left text-[12.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-40"
              >
                {elem.cimke}
              </button>
            ))}
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

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-text-muted">
        {DISZPO_SZINEK.map((szin) => (
          <span key={szin} className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-sm" style={{ backgroundColor: SZIN_LEIRAS[szin].hatter }} />
            {SZIN_LEIRAS[szin].jelentes}
          </span>
        ))}
        <span className="ml-auto">
          Nyilak: mozgás · gépelés vagy Enter: szerkesztés · Ctrl+C: másolás (színnel) · Ctrl+V: beillesztés · Shift+nyíl vagy húzás: tartomány
          · Delete: tartalom törlése · jobb gomb: sor/oszlop (beszúrás, elrejtés)
        </span>
      </div>
    </div>
  );
}
