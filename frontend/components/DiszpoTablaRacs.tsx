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

  const sorSzam = Math.max(munkalap.sor_szam, munkalap.sorok.length);
  const oszlopSzam = munkalap.oszlop_szam;

  // Az első oszlopok BEFAGYASZTVA: 146 oszlopnál a dátum nélkül nem lehet
  // tudni, melyik sorban vagyunk. Ahol nincs dátum-oszlop, ott egy elég.
  const fagyasztott = munkalap.sorok.some((s) => s.datum) ? 3 : 1;
  const fagyasztottSzeles = fagyasztott * OSZLOP_SZELES;

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
  const oszlopTerkep = useMemo(() => new Map(munkalap.oszlopok.map((o) => [o.idx, o])), [munkalap.oszlopok]);

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
  const elsoSor = Math.max(munkalap.fejlec_sorok, Math.floor(gorgetes.top / SOR_MAGASSAG) - RATARTAS);
  const utolsoSor = Math.min(sorSzam, Math.ceil((gorgetes.top + meret.magas) / SOR_MAGASSAG) + RATARTAS);
  const elsoOszlop = Math.max(
    fagyasztott,
    Math.floor((gorgetes.left - fagyasztottSzeles) / OSZLOP_SZELES) - RATARTAS,
  );
  const utolsoOszlop = Math.min(
    oszlopSzam,
    Math.ceil((gorgetes.left + meret.szeles - fagyasztottSzeles) / OSZLOP_SZELES) + RATARTAS,
  );

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
      const uj = {
        sor: Math.min(Math.max(kijelolt.sor + dSor, munkalap.fejlec_sorok), sorSzam - 1),
        oszlop: Math.min(Math.max(kijelolt.oszlop + dOszlop, 0), oszlopSzam - 1),
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
      const y = uj.sor * SOR_MAGASSAG;
      const x = fagyasztottSzeles + (uj.oszlop - fagyasztott) * OSZLOP_SZELES;
      if (y < elem.scrollTop) elem.scrollTop = y;
      if (y + SOR_MAGASSAG > elem.scrollTop + elem.clientHeight)
        elem.scrollTop = y + SOR_MAGASSAG - elem.clientHeight;
      if (uj.oszlop >= fagyasztott) {
        if (x < elem.scrollLeft + fagyasztottSzeles) elem.scrollLeft = x - fagyasztottSzeles;
        if (x + OSZLOP_SZELES > elem.scrollLeft + elem.clientWidth)
          elem.scrollLeft = x + OSZLOP_SZELES - elem.clientWidth;
      }
    },
    [kijelolt, tartomany, sorSzam, oszlopSzam, munkalap.fejlec_sorok, fagyasztott, fagyasztottSzeles],
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

  function cellaStilus(szin: string | null | undefined): React.CSSProperties {
    if (!szin || !(szin in SZIN_LEIRAS)) return {};
    const s = SZIN_LEIRAS[szin as DiszpoSzin];
    return { backgroundColor: s.hatter, color: s.szoveg };
  }

  function kijeloltE(sor: number, oszlop: number): boolean {
    if (!tartomany) return kijelolt.sor === sor && kijelolt.oszlop === oszlop;
    const { sor1, sor2, oszlop1, oszlop2 } = normalizal(tartomany);
    return sor >= sor1 && sor <= sor2 && oszlop >= oszlop1 && oszlop <= oszlop2;
  }

  /** Egy cella kirajzolása - abszolút pozícióval (a virtualizálás miatt). */
  function Cella({ sor, oszlop, fagyott }: { sor: number; oszlop: number; fagyott: boolean }) {
    const c = cella(sor, oszlop);
    const s = sorTerkep.get(sor);
    const szerkesztettE = szerkesztes?.pont.sor === sor && szerkesztes?.pont.oszlop === oszlop;
    const bal = fagyott ? oszlop * OSZLOP_SZELES : fagyasztottSzeles + (oszlop - fagyasztott) * OSZLOP_SZELES;
    return (
      <div
        style={{
          position: "absolute",
          top: sor * SOR_MAGASSAG,
          left: fagyott ? bal + gorgetes.left : bal,
          width: OSZLOP_SZELES,
          height: SOR_MAGASSAG,
          zIndex: fagyott ? 2 : undefined,
          ...cellaStilus(c?.szin),
        }}
        className={`overflow-hidden border-b border-r border-border px-1.5 text-[12px] leading-[24px] ${
          s?.elvalaszto ? "bg-surface-3 font-medium" : ""
        } ${kijeloltE(sor, oszlop) ? "outline outline-2 -outline-offset-2 outline-text-accent" : ""} ${
          fagyott && !c?.szin ? "bg-surface-2" : ""
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
          <span className="block truncate">{c?.ertek ?? ""}</span>
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
            const fagyott = c < fagyasztott;
            const bal = fagyott
              ? c * OSZLOP_SZELES + gorgetes.left
              : fagyasztottSzeles + (c - fagyasztott) * OSZLOP_SZELES;
            return (
              <div
                key={c}
                style={{ position: "absolute", left: bal - gorgetes.left, width: OSZLOP_SZELES, zIndex: fagyott ? 2 : 1 }}
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
                style={{ position: "absolute", top: r * SOR_MAGASSAG - (r < munkalap.fejlec_sorok ? 0 : gorgetes.top), height: SOR_MAGASSAG }}
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
                width: fagyasztottSzeles + Math.max(oszlopSzam - fagyasztott, 0) * OSZLOP_SZELES,
                height: sorSzam * SOR_MAGASSAG,
                position: "relative",
              }}
            >
              {/* FEJLÉC-SOROK: fent ragadnak. */}
              {fejlecSorok.map((r) => (
                <div key={`f${r}`} style={{ position: "sticky", top: 0, zIndex: 3, height: 0 }}>
                  <div style={{ position: "absolute", top: r * SOR_MAGASSAG - 0, left: 0, right: 0 }}>
                    {[...fagyasztottOszlopok, ...lathatoOszlopok].map((c) => {
                      const cl = cella(r, c);
                      const fagyott = c < fagyasztott;
                      const bal = fagyott
                        ? c * OSZLOP_SZELES + gorgetes.left
                        : fagyasztottSzeles + (c - fagyasztott) * OSZLOP_SZELES;
                      return (
                        <div
                          key={c}
                          style={{
                            position: "absolute",
                            left: bal,
                            width: OSZLOP_SZELES,
                            height: SOR_MAGASSAG,
                            zIndex: fagyott ? 2 : 1,
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

              {lathatoSorok.map((r) => (
                <div key={r}>
                  {fagyasztottOszlopok.map((c) => (
                    <Cella key={`fx${c}`} sor={r} oszlop={c} fagyott />
                  ))}
                  {lathatoOszlopok.map((c) => (
                    <Cella key={c} sor={r} oszlop={c} fagyott={false} />
                  ))}
                </div>
              ))}
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
          Nyilak: mozgás · gépelés vagy Enter: szerkesztés · Shift+nyíl vagy húzás: tartomány · Delete: tartalom
          törlése · jobb gomb: sor/oszlop
        </span>
      </div>
    </div>
  );
}
