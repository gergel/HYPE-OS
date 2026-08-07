"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowDown, ArrowUp, Download, RefreshCw, Search } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import type { UtalasraVaroTetel } from "@/lib/api";
import { formatFt } from "@/lib/ido";

/** Ennyi tétel látszik alapból - a többi egy kattintással nyitható. A lista
 * hosszú tud lenni, és utaláskor úgyis a legsürgetőbb (legkorábbi határidejű)
 * tételekkel kezdünk, azok pedig elöl vannak. */
const ELSO_ADAG = 10;

/** Amire rendezni lehet. A "hatarido" az alapértelmezés: a legkorábbi (már
 * lejárt) határidejű tételt kell először utalni. */
type Rendezes = "hatarido" | "megnevezes" | "kinek" | "tipus" | "osszeg";

/** Fedezettség-csoportok. A LÉNYEG az első: azok a tételek, amiknél a
 * megrendelő már kifizette a projektkódot, tehát a pénz nálunk van - ezek
 * mehetnek nyugodtan utalásra. A backend számolja (lásd routes/finance.py
 * _fedezettseg), itt csak csoportosítunk. */
const FEDEZET_CSOPORTOK: { kulcs: string; cimke: string; leiras: string }[] = [
  {
    kulcs: "fedezett",
    cimke: "Utalható",
    leiras: "A projektkódot a megrendelő már kifizette - a fedezet megérkezett.",
  },
  {
    kulcs: "var",
    cimke: "Fedezetre vár",
    leiras: "A projektkód még nincs kifizetve: a pénz még nem jött be erre a munkára.",
  },
  {
    kulcs: "reszben",
    cimke: "Részben fedezett",
    leiras:
      "Összevont tétel (pl. havi belsős TIG több projekt extráival): a projektkódok egy részét már kifizették, a többit még nem.",
  },
  {
    kulcs: "nincs_projektkod",
    cimke: "Nincs projektkód",
    leiras: "Nincs projektkódhoz kötve, ezért a fedezet nem eldönthető - itt kézzel kell mérlegelni.",
  },
];

const FEDEZET_SZIN: Record<string, string> = {
  fedezett: "text-text-green",
  var: "text-text-orange",
  reszben: "text-text-blue",
  nincs_projektkod: "text-text-muted",
};

const OSZLOPOK: { kulcs: Rendezes; cimke: string }[] = [
  { kulcs: "megnevezes", cimke: "Tétel" },
  { kulcs: "kinek", cimke: "Kinek" },
  { kulcs: "tipus", cimke: "Típus" },
  { kulcs: "hatarido", cimke: "Fizetési határidő" },
];

/** Rendezési kulcs egy tételhez. A hiányzó érték MINDIG a lista végére kerül
 * (a határidő nélküli tételt nem lehet sürgősnek venni), ezért külön jelzőt
 * adunk vissza mellé. */
function rendezesiKulcs(tetel: UtalasraVaroTetel, szerint: Rendezes): [number, string | number] {
  if (szerint === "osszeg") return [tetel.osszeg === null ? 1 : 0, tetel.osszeg ?? 0];
  if (szerint === "hatarido") return [tetel.hatarido === null ? 1 : 0, tetel.hatarido ?? ""];
  const ertek = szerint === "megnevezes" ? tetel.megnevezes : szerint === "kinek" ? tetel.kinek : tetel.tipus;
  return [ertek ? 0 : 1, (ertek ?? "").toLocaleLowerCase("hu-HU")];
}

/** Utalásra váró számlák: ami már megérkezett hozzánk számlaként, de még nem
 * utaltuk el (kiadások, külsős és belsős TIG-ek egy listában).
 *
 * A lényeg a kijelölés: az utalási körhöz ki lehet pipálni a tételeket, és a
 * hozzájuk tartozó számlák EGYETLEN ZIP-ben letölthetők - így nem kell
 * egyenként végigkattintani három különböző listát. A kijelölt tételek összege
 * is látszik, hogy az utalás előtt legyen mihez hasonlítani. */
export function UtalasraVaroSzamlak({ kezdeti }: { kezdeti: UtalasraVaroTetel[] }) {
  const [tetelek, setTetelek] = useState(kezdeti);
  const [kijelolt, setKijelolt] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [mindMutat, setMindMutat] = useState(false);
  const [kereses, setKereses] = useState("");
  const [tipusSzuro, setTipusSzuro] = useState("");
  const [rendezes, setRendezes] = useState<Rendezes>("hatarido");
  // Alapból az UTALHATÓKAT mutatjuk: a kérdés az utalási körnél mindig az,
  // hogy kinek mehet a pénz. A többi csoport egy kattintásra van, a
  // darabszámuk pedig végig látszik, hogy semmi ne tűnjön el csendben.
  const [fedezetSzuro, setFedezetSzuro] = useState<string>("fedezett");
  const [novekvo, setNovekvo] = useState(true);

  // A szerverről frissen kapott lista felülírja a helyben tartottat (amit a
  // "Frissítés" gomb tölt újra). Renderelés közbeni igazítás, nem useEffect:
  // így nincs egy felesleges, elavult adattal megrajzolt kör.
  const [elozoKezdeti, setElozoKezdeti] = useState(kezdeti);
  if (kezdeti !== elozoKezdeti) {
    setElozoKezdeti(kezdeti);
    setTetelek(kezdeti);
  }

  // Ami közben eltűnt a listáról (mert kifizetettre került), az a kijelölésből
  // is essen ki - különben egy már elutalt tétel is bekerülne a csomagba.
  const letezoKulcsok = useMemo(() => new Set(tetelek.map((t) => t.kulcs)), [tetelek]);
  const aktivKijeloles = useMemo(
    () => [...kijelolt].filter((k) => letezoKulcsok.has(k)),
    [kijelolt, letezoKulcsok],
  );

  const kijeloltOsszeg = tetelek
    .filter((t) => aktivKijeloles.includes(t.kulcs))
    .reduce((sum, t) => sum + (t.osszeg ?? 0), 0);

  // Szűrés (keresés + típus) és rendezés. A KIJELÖLÉS ettől független: ami ki
  // van pipálva, az a szűrő átállítása után is kijelölve marad, különben egy
  // gyors keresés csendben kidobálna tételeket az utalási körből.
  const tipusok = useMemo(() => [...new Set(tetelek.map((t) => t.tipus))].sort(), [tetelek]);
  const csoportDarab = useMemo(() => {
    const szamok: Record<string, number> = {};
    for (const t of tetelek) szamok[t.fedezettseg] = (szamok[t.fedezettseg] ?? 0) + 1;
    return szamok;
  }, [tetelek]);
  const szurt = useMemo(() => {
    const keresett = kereses.trim().toLocaleLowerCase("hu-HU");
    const talalatok = tetelek.filter((t) => {
      if (fedezetSzuro && t.fedezettseg !== fedezetSzuro) return false;
      if (tipusSzuro && t.tipus !== tipusSzuro) return false;
      if (!keresett) return true;
      return [t.megnevezes, t.kinek, t.tipus, t.hatarido].some((mezo) =>
        (mezo ?? "").toLocaleLowerCase("hu-HU").includes(keresett),
      );
    });
    const irany = novekvo ? 1 : -1;
    return [...talalatok].sort((a, b) => {
      const [aHianyzik, aErtek] = rendezesiKulcs(a, rendezes);
      const [bHianyzik, bErtek] = rendezesiKulcs(b, rendezes);
      if (aHianyzik !== bHianyzik) return aHianyzik - bHianyzik;
      if (aErtek < bErtek) return -irany;
      if (aErtek > bErtek) return irany;
      return a.megnevezes.localeCompare(b.megnevezes, "hu-HU");
    });
  }, [tetelek, kereses, tipusSzuro, fedezetSzuro, rendezes, novekvo]);

  const mindKijelolve = szurt.length > 0 && szurt.every((t) => kijelolt.has(t.kulcs));

  function valt(kulcs: string) {
    setKijelolt((elozo) => {
      const uj = new Set(elozo);
      if (uj.has(kulcs)) uj.delete(kulcs);
      else uj.add(kulcs);
      return uj;
    });
  }

  /** A fejléc pipája a SZŰRT tételekre vonatkozik - így lehet egy típust (pl.
   * a belsős TIG-eket) egy mozdulattal az utalási körbe tenni. */
  function mindet() {
    setKijelolt((elozo) => {
      const uj = new Set(elozo);
      for (const t of szurt) {
        if (mindKijelolve) uj.delete(t.kulcs);
        else uj.add(t.kulcs);
      }
      return uj;
    });
  }

  /** Ugyanarra az oszlopra kattintva megfordul az irány. */
  function rendezz(szerint: Rendezes) {
    if (szerint === rendezes) setNovekvo((elozo) => !elozo);
    else {
      setRendezes(szerint);
      setNovekvo(true);
    }
  }

  async function frissit() {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch("/api/v1/finance/utalasra-varo");
      if (res.ok) setTetelek(await res.json());
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function letolt() {
    if (aktivKijeloles.length === 0) return;
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch("/api/v1/finance/utalasra-varo/zip", {
        method: "POST",
        body: JSON.stringify({ kulcsok: aktivKijeloles }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen letöltés (HTTP ${res.status})`);
        return;
      }
      // A végpont bejelentkezést igényel, ezért nem lehet sima <a href> - a
      // választ blobként mentjük le (ugyanaz a minta, mint a havi csomagnál).
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const ma = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      a.download = `utalasra_varo_szamlak_${ma}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setHiba(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (tetelek.length === 0) {
    return (
      <p className="text-[13px] text-text-muted">
        Nincs utalásra váró számla - minden feltöltött számla ki van fizetve.
      </p>
    );
  }

  const ma = new Date().toISOString().slice(0, 10);
  // A lenyitás csak azt szabályozza, mennyi látszik a szűrt listából - a ZIP
  // továbbra is a kijelölt tételekkel megy, akkor is, ha épp nem látszanak.
  const lathato = mindMutat ? szurt : szurt.slice(0, ELSO_ADAG);
  const rejtett = szurt.length - lathato.length;
  const szurtOsszeg = szurt.reduce((sum, t) => sum + (t.osszeg ?? 0), 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={busy || aktivKijeloles.length === 0}
          onClick={letolt}
          className="btn btn-primary inline-flex items-center gap-1.5 disabled:opacity-50"
        >
          <Download size={14} />
          {busy ? "Készül…" : `Kijelöltek számlái ZIP-ben (${aktivKijeloles.length})`}
        </button>
        <span className="text-[13px] text-text-secondary">
          Kijelölve: <span className="font-medium text-text-primary tabular-nums">{formatFt(kijeloltOsszeg)}</span>
        </span>
        <button
          type="button"
          disabled={busy}
          onClick={frissit}
          className="inline-flex items-center gap-1.5 text-[12.5px] text-text-secondary hover:text-text-primary disabled:opacity-50"
        >
          <RefreshCw size={13} />
          Frissítés
        </button>
        {hiba && <span className="text-[12.5px] text-text-danger">{hiba}</span>}
      </div>

      {/* Fedezettség szerinti csoportok - elöl az, ami most utalható. */}
      <div className="flex flex-wrap items-center gap-1.5">
        {FEDEZET_CSOPORTOK.map((csoport) => {
          const darab = csoportDarab[csoport.kulcs] ?? 0;
          const aktiv = fedezetSzuro === csoport.kulcs;
          return (
            <button
              key={csoport.kulcs}
              type="button"
              title={csoport.leiras}
              onClick={() => setFedezetSzuro(csoport.kulcs)}
              className={`rounded-[var(--radius)] border px-2.5 py-1.5 text-[12.5px] ${
                aktiv
                  ? "border-text-accent/50 bg-bg-accent text-text-accent"
                  : "border-border text-text-secondary hover:bg-surface-3"
              }`}
            >
              {csoport.cimke} ({darab})
            </button>
          );
        })}
        <button
          type="button"
          onClick={() => setFedezetSzuro("")}
          className={`rounded-[var(--radius)] border px-2.5 py-1.5 text-[12.5px] ${
            fedezetSzuro === ""
              ? "border-text-accent/50 bg-bg-accent text-text-accent"
              : "border-border text-text-secondary hover:bg-surface-3"
          }`}
        >
          Mind ({tetelek.length})
        </button>
      </div>
      <p className="-mt-2 text-[12px] text-text-muted">
        {FEDEZET_CSOPORTOK.find((cs) => cs.kulcs === fedezetSzuro)?.leiras ??
          "Minden utalásra váró tétel, fedezettségtől függetlenül."}
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <label className="relative">
          <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            type="search"
            value={kereses}
            onChange={(e) => setKereses(e.target.value)}
            placeholder="Keresés (tétel, név, típus, határidő)"
            aria-label="Keresés az utalásra váró tételek közt"
            className="w-72 rounded-[var(--radius)] border border-border bg-surface-2 py-1.5 pl-7 pr-2 text-[13px] text-text-primary focus:outline-none"
          />
        </label>
        <select
          value={tipusSzuro}
          onChange={(e) => setTipusSzuro(e.target.value)}
          aria-label="Szűrés típusra"
          className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
        >
          <option value="">Minden típus</option>
          {tipusok.map((tipus) => (
            <option key={tipus} value={tipus}>
              {tipus}
            </option>
          ))}
        </select>
        {(kereses || tipusSzuro) && (
          <button
            type="button"
            onClick={() => {
              setKereses("");
              setTipusSzuro("");
            }}
            className="text-[12.5px] text-text-secondary hover:text-text-primary hover:underline"
          >
            Szűrők törlése ({szurt.length}/{tetelek.length})
          </button>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="os-table w-full border-collapse text-[13px]">
          <thead>
            <tr>
              <th className="w-8">
                <input
                  type="checkbox"
                  checked={mindKijelolve}
                  onChange={mindet}
                  aria-label="Mindet kijelöl"
                  className="cursor-pointer"
                />
              </th>
              {OSZLOPOK.map((oszlop) => (
                <th key={oszlop.kulcs} className="text-left">
                  <button
                    type="button"
                    onClick={() => rendezz(oszlop.kulcs)}
                    className="inline-flex items-center gap-1 hover:text-text-primary"
                  >
                    {oszlop.cimke}
                    {rendezes === oszlop.kulcs &&
                      (novekvo ? <ArrowUp size={12} aria-label="növekvő" /> : <ArrowDown size={12} aria-label="csökkenő" />)}
                  </button>
                </th>
              ))}
              <th className="text-left">Fedezet</th>
              <th className="text-right">Számlák</th>
              <th className="text-right">
                <button
                  type="button"
                  onClick={() => rendezz("osszeg")}
                  className="inline-flex items-center gap-1 hover:text-text-primary"
                >
                  Összeg
                  {rendezes === "osszeg" &&
                    (novekvo ? <ArrowUp size={12} aria-label="növekvő" /> : <ArrowDown size={12} aria-label="csökkenő" />)}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {lathato.map((t) => {
              const lejart = t.hatarido !== null && t.hatarido < ma;
              return (
                <tr key={t.kulcs}>
                  <td>
                    <input
                      type="checkbox"
                      checked={aktivKijeloles.includes(t.kulcs)}
                      onChange={() => valt(t.kulcs)}
                      aria-label={`${t.megnevezes} kijelölése`}
                      className="cursor-pointer"
                    />
                  </td>
                  <td>
                    {t.link ? (
                      <Link href={t.link} className="text-text-accent hover:underline">
                        {t.megnevezes}
                      </Link>
                    ) : (
                      t.megnevezes
                    )}
                  </td>
                  <td className="text-text-secondary">{t.kinek ?? "–"}</td>
                  <td className="text-text-secondary">{t.tipus}</td>
                  {/* A lejárt határidő pirosan: ezeket kell először utalni. */}
                  <td className={lejart ? "text-text-danger" : "text-text-secondary"}>{t.hatarido ?? "–"}</td>
                  {/* Fedezet: melyik projektkódon jött be a pénz, és melyiken
                      nem - összevont tételnél több kód is szerepelhet. */}
                  <td className={`text-[12.5px] ${FEDEZET_SZIN[t.fedezettseg] ?? "text-text-secondary"}`}>
                    {FEDEZET_CSOPORTOK.find((cs) => cs.kulcs === t.fedezettseg)?.cimke ?? t.fedezettseg}
                    {t.projektkodok.length > 0 && (
                      <span className="block text-text-muted">
                        {t.fedezetlen_projektkodok.length > 0
                          ? `vár: ${t.fedezetlen_projektkodok.join(", ")}`
                          : t.projektkodok.join(", ")}
                      </span>
                    )}
                  </td>
                  <td className="text-right tabular-nums text-text-secondary">{t.szamla_db}</td>
                  <td className="text-right tabular-nums">{t.osszeg === null ? "–" : formatFt(t.osszeg)}</td>
                </tr>
              );
            })}
            {rejtett > 0 && (
              <tr>
                <td colSpan={8} className="py-2">
                  <button
                    type="button"
                    onClick={() => setMindMutat(true)}
                    className="text-[12.5px] text-text-accent hover:underline"
                  >
                    További {rejtett} tétel mutatása
                  </button>
                </td>
              </tr>
            )}
            {mindMutat && tetelek.length > ELSO_ADAG && (
              <tr>
                <td colSpan={8} className="py-2">
                  <button
                    type="button"
                    onClick={() => setMindMutat(false)}
                    className="text-[12.5px] text-text-secondary hover:text-text-primary hover:underline"
                  >
                    Csak az első {ELSO_ADAG} mutatása
                  </button>
                </td>
              </tr>
            )}
            {szurt.length === 0 && (
              <tr>
                <td colSpan={8} className="py-3 text-text-muted">
                  Nincs a keresésnek megfelelő tétel.
                </td>
              </tr>
            )}
            <tr className="font-medium">
              <td colSpan={7} className="text-text-secondary">
                Összesen ({szurt.length} tétel
                {szurt.length !== tetelek.length && ` a ${tetelek.length}-ból szűrve`})
              </td>
              <td className="text-right tabular-nums text-text-primary">{formatFt(szurtOsszeg)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
