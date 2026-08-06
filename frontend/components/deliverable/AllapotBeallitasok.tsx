"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import type { AllapotBeallitas } from "@/lib/api";

/** Alapszínek, amiket egy kattintással lehet választani - a színválasztóval
 * bármi más is beállítható. Halványan kerülnek a táblára, ezért itt telített
 * árnyalatok állnak: a keverést a tábla végzi (lásd DeliverableBoard). */
const SZIN_MINTAK = ["#6d8f72", "#c98b5a", "#7f8ec4", "#b06a8f", "#5f9ea0", "#a8a05a", "#8a8a8a"];

/** Az Utómunka tábla oszlopainak beállítása: milyen SORRENDBEN jöjjenek az
 * állapotok, milyen SZÍNT kapjanak, és melyik számít elkészültnek.
 *
 * Az "elkészült" jelölésnek tétje van: ami ilyen állapotban áll, az nem kerül
 * a lejárt határidejű anyagok közé a dashboardon - a munka ott már megvan
 * (lásd backend routes/dashboard.py).
 *
 * A lista az összes VÁLASZTHATÓ állapotot tartalmazza (a mező-beállításokból),
 * tehát egy új állapot felvétele után az is itt jelenik meg, a végén. */
export function AllapotBeallitasok({
  allapotok,
  kezdeti,
  mezoValasztek,
  kezdetiKartyaMezok,
}: {
  allapotok: string[];
  kezdeti: AllapotBeallitas[];
  /** Miből lehet választani a kártyán megjelenő adatokhoz. */
  mezoValasztek: { kulcs: string; cimke: string }[];
  kezdetiKartyaMezok: string[];
}) {
  const router = useRouter();
  const [nyitva, setNyitva] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ujAllapot, setUjAllapot] = useState("");
  const [kartyaMezok, setKartyaMezok] = useState<string[]>(kezdetiKartyaMezok);

  // A választható állapotok a mérvadóak; a mentett beállítás csak sorrendet és
  // színt ad hozzájuk. Ami be van állítva, az elöl, a beállított sorrendben;
  // ami még nincs, az a végén.
  const [sorok, setSorok] = useState<AllapotBeallitas[]>(() => {
    const mentett = new Map(kezdeti.map((b) => [b.allapot, b]));
    const beallitottak = kezdeti.filter((b) => allapotok.includes(b.allapot));
    const ujak = allapotok
      .filter((a) => !mentett.has(a))
      .map((allapot) => ({ allapot, sorrend: 0, szin: null, kesz_allapot: false }));
    return [...beallitottak, ...ujak];
  });

  function mozgat(index: number, irany: -1 | 1) {
    setSorok((elozo) => {
      const cel = index + irany;
      if (cel < 0 || cel >= elozo.length) return elozo;
      const uj = [...elozo];
      [uj[index], uj[cel]] = [uj[cel], uj[index]];
      return uj;
    });
  }

  function modosit(index: number, mezok: Partial<AllapotBeallitas>) {
    setSorok((elozo) => elozo.map((sor, i) => (i === index ? { ...sor, ...mezok } : sor)));
  }

  /** Új oszlop felvétele. Enélkül egy olyan állapot, amiben épp EGYETLEN anyag
   * sincs (pl. "Javítás", miután mindegyiket továbbléptették), nem tudna
   * megjelenni a táblán - és nem is lehetne rátenni semmit. */
  function allapotHozzaad() {
    const nev = ujAllapot.trim();
    if (!nev || sorok.some((sor) => sor.allapot === nev)) return;
    setSorok((elozo) => [...elozo, { allapot: nev, sorrend: elozo.length, szin: null, kesz_allapot: false }]);
    setUjAllapot("");
  }

  function allapotTorol(index: number) {
    setSorok((elozo) => elozo.filter((_, i) => i !== index));
  }

  function kartyaMezoValt(kulcs: string) {
    setKartyaMezok((elozo) => (elozo.includes(kulcs) ? elozo.filter((k) => k !== kulcs) : [...elozo, kulcs]));
  }

  async function ment() {
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/deliverables/allapot-beallitasok", {
        method: "PUT",
        body: JSON.stringify({
          beallitasok: sorok.map((sor, index) => ({ ...sor, sorrend: index })),
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      const mezoRes = await authFetch("/api/v1/deliverables/kartya-mezok", {
        method: "PUT",
        body: JSON.stringify({ kartya_mezok: kartyaMezok }),
      });
      if (!mezoRes.ok) {
        const detail = await mezoRes.json().catch(() => null);
        alert(`A kártya-mezők mentése nem sikerült: ${detail?.detail ?? mezoRes.status}`);
        return;
      }
      router.refresh();
      setNyitva(false);
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (!nyitva) {
    return (
      <button
        type="button"
        onClick={() => setNyitva(true)}
        className="text-[12.5px] text-text-secondary hover:text-text-primary hover:underline"
      >
        Nézet beállítása
      </button>
    );
  }

  return (
    <div className="w-full rounded-[var(--radius)] border border-border bg-surface-3 p-3">
      <p className="mb-1 text-[13px] font-medium text-text-primary">Oszlopok sorrendje és színe</p>
      <p className="mb-3 text-[12px] text-text-muted">
        A nyilakkal állítható, melyik oszlop melyik után jöjjön. A szín halványan kerül az oszlopra és a benne lévő
        kártyákra. Az &quot;elkészült&quot; állapotú anyag nem jelenik meg lejárt határidejűként.
      </p>
      <div className="space-y-1.5">
        {sorok.map((sor, index) => (
          <div key={sor.allapot} className="flex flex-wrap items-center gap-2 text-[13px]">
            <span className="flex gap-0.5">
              <button
                type="button"
                onClick={() => mozgat(index, -1)}
                disabled={index === 0}
                aria-label={`${sor.allapot} feljebb`}
                className="rounded-[var(--radius)] border border-border p-1 text-text-secondary hover:bg-surface-2 disabled:opacity-30"
              >
                <ArrowUp size={12} />
              </button>
              <button
                type="button"
                onClick={() => mozgat(index, 1)}
                disabled={index === sorok.length - 1}
                aria-label={`${sor.allapot} lejjebb`}
                className="rounded-[var(--radius)] border border-border p-1 text-text-secondary hover:bg-surface-2 disabled:opacity-30"
              >
                <ArrowDown size={12} />
              </button>
            </span>
            <span className="min-w-[140px] text-text-primary">{sor.allapot}</span>
            <input
              type="color"
              value={sor.szin ?? "#8a8a8a"}
              onChange={(e) => modosit(index, { szin: e.target.value })}
              aria-label={`${sor.allapot} színe`}
              className="h-6 w-8 cursor-pointer rounded border border-border bg-transparent"
            />
            <span className="flex gap-1">
              {SZIN_MINTAK.map((minta) => (
                <button
                  key={minta}
                  type="button"
                  onClick={() => modosit(index, { szin: minta })}
                  aria-label={`${sor.allapot}: ${minta}`}
                  style={{ background: minta }}
                  className="h-4 w-4 rounded-full border border-border"
                />
              ))}
              {sor.szin && (
                <button
                  type="button"
                  onClick={() => modosit(index, { szin: null })}
                  className="text-[12px] text-text-secondary hover:text-text-primary hover:underline"
                >
                  szín nélkül
                </button>
              )}
            </span>
            <label className="flex cursor-pointer items-center gap-1.5 text-text-secondary">
              <input
                type="checkbox"
                checked={sor.kesz_allapot}
                onChange={(e) => modosit(index, { kesz_allapot: e.target.checked })}
                className="cursor-pointer"
              />
              Elkészült
            </label>
            <button
              type="button"
              onClick={() => allapotTorol(index)}
              aria-label={`${sor.allapot} oszlop törlése`}
              className="text-[12px] text-text-secondary hover:text-text-danger hover:underline"
            >
              Oszlop törlése
            </button>
          </div>
        ))}
        {sorok.length === 0 && <p className="text-[12.5px] text-text-muted">Nincs felvett állapot.</p>}
      </div>

      {/* Új oszlop: egy állapot akkor is kell a táblára, ha épp egyetlen anyag
          sincs benne - különben nem is lehetne odatenni egyet. */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <input
          value={ujAllapot}
          onChange={(e) => setUjAllapot(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              allapotHozzaad();
            }
          }}
          placeholder="Új oszlop neve (pl. Javítás)"
          aria-label="Új állapot neve"
          className="w-56 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
        />
        <button
          type="button"
          onClick={allapotHozzaad}
          disabled={!ujAllapot.trim()}
          className="rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-[12.5px] text-text-secondary hover:bg-surface-2 disabled:opacity-40"
        >
          + Oszlop hozzáadása
        </button>
      </div>

      {/* Mi látszódjon a kártyákon */}
      <div className="mt-4 border-t border-border pt-3">
        <p className="mb-1 text-[13px] font-medium text-text-primary">Mi látszódjon a kártyákon</p>
        <p className="mb-2 text-[12px] text-text-muted">
          Az anyag neve mindig látszik. Ha egyet sem választasz, a határidő és a kiosztott ember jelenik meg (ez az
          alapértelmezés).
        </p>
        <div className="flex max-h-48 flex-wrap gap-x-4 gap-y-1 overflow-y-auto">
          {mezoValasztek.map((mezo) => (
            <label
              key={mezo.kulcs}
              className="flex cursor-pointer items-center gap-1.5 text-[12.5px] text-text-secondary"
            >
              <input
                type="checkbox"
                checked={kartyaMezok.includes(mezo.kulcs)}
                onChange={() => kartyaMezoValt(mezo.kulcs)}
                className="cursor-pointer"
              />
              {mezo.cimke}
            </label>
          ))}
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <button type="button" disabled={busy} onClick={ment} className="btn btn-primary disabled:opacity-50">
          {busy ? "Mentés…" : "Mentés"}
        </button>
        <button
          type="button"
          onClick={() => setNyitva(false)}
          className="text-[12.5px] text-text-secondary hover:text-text-primary hover:underline"
        >
          Mégse
        </button>
      </div>
    </div>
  );
}
