"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
// A pénzformázó a FÜGGŐSÉG NÉLKÜLI modulból jön: a lib/api.ts a
// "next/headers"-t is behúzza, amit kliens komponensbe nem lehet bevinni.
import { devizas, formatHuf, penznemKod, penzzel, PENZNEMEK } from "@/lib/penz";

/** MENNYIÉRT csináltuk ezt a munkát: nettó összeg + "+ÁFA".
 *
 * Miért külön, jól látható helyen? Mert az összeget gyakran MÁS tudja, mint
 * aki a szerződést és a TIG-et készíti - eddig viszont csak a papírok
 * űrlapjában (vagy a mezőrács mélyén) lehetett megadni, tehát aki tudta a
 * számot, annak egy szerződés-piszkozaton át kellett volna beírnia.
 *
 * Ez a szám a projektkód SAJÁT mezője (nem a papíroké): innen tölti elő magát
 * a szerződés és a TIG, ebből számol a számla-lépés, és ha a munka nem a
 * bevételek közé kerül, ez adja a projekt bevételét is - vagyis ebből lesz a
 * profit (lásd backend services/projektkod_osszeg.py).
 *
 * A "+ÁFA" a Notionból örökölt SZÖVEGES mező ("+ÁFA"), ezért írunk vissza
 * szöveget, nem igaz/hamis értéket - így a régi sorok és az új beírás
 * ugyanazt jelenti mindenhol. */
export function VallalasiAr({
  patchPath,
  netto,
  pluszAfa,
  canEdit,
  /** Honnan való a szám, ha nem itt adták meg (TIG / szerződés) - ilyenkor
   * csak tájékoztatunk, nem írjuk felül. */
  papirbolNetto,
  /** Milyen pénznemben vállaltuk, és milyen árfolyamon számolunk. A BEVÉTEL
   * ezzel átváltva, forintban kerül a Pénzügyekbe (lásd backend
   * services/penznem.py) - a vállalási ár viszont abban a pénznemben marad,
   * amiben megállapodtunk, mert a szerződésen és a TIG-en az áll. */
  penznem = "HUF",
  arfolyam = null,
}: {
  patchPath: string;
  netto: number | null;
  pluszAfa: string | null;
  canEdit: boolean;
  papirbolNetto: number | null;
  penznem?: string;
  arfolyam?: number | null;
}) {
  const router = useRouter();
  const [ertek, setErtek] = useState(netto === null ? "" : String(netto));
  const [afa, setAfa] = useState(!!pluszAfa && pluszAfa.toLowerCase().includes("fa"));
  // A NORMALIZÁLT kóddal dolgozunk: a régi projektkódokon "Forint" áll (a
  // Notion szabad select-je), a választó viszont HUF/EUR/USD értékekkel megy -
  // enélkül a mező üresnek látszott, és a szerver ismeretlen pénznemet
  // kiabált egy teljesen szokásos forintos munkára.
  const [valuta, setValuta] = useState(penznemKod(penznem));
  const [arfolyamErtek, setArfolyamErtek] = useState(arfolyam === null ? "" : String(arfolyam));
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  const szam = ertek.trim() === "" ? null : Number(ertek.replace(/\s/g, "").replace(",", "."));
  const ervenyes = szam === null || Number.isFinite(szam);
  const bruttoErtek = szam === null || !ervenyes ? null : afa ? Math.round(szam * 1.27 * 100) / 100 : szam;
  const arfolyamSzam = arfolyamErtek.trim() === "" ? null : Number(arfolyamErtek.replace(",", "."));
  // Ennyi lesz belőle a Pénzügyekben - devizás munkánál ez a szám a lényeg.
  const forintban =
    !devizas(valuta) || szam === null || arfolyamSzam === null || !Number.isFinite(arfolyamSzam)
      ? null
      : Math.round(szam * arfolyamSzam * 100) / 100;

  async function ment(adat: Record<string, unknown>) {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify(adat) });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        setHiba(reszlet?.detail ?? `Sikertelen mentés (HTTP ${res.status})`);
        return;
      }
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-3">
        <label className="block text-[13px] text-text-secondary">
          Nettó összeg ({valuta})
          <input
            type="text"
            inputMode="numeric"
            value={ertek}
            disabled={!canEdit || busy}
            placeholder="Nincs megadva"
            onChange={(e) => setErtek(e.target.value)}
            onBlur={() => {
              if (!ervenyes) return;
              if (szam === netto) return;
              ment({ netto_osszeg: szam });
            }}
            className="mt-1 w-40 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary disabled:opacity-60"
          />
        </label>
        <label className="flex cursor-pointer items-center gap-2 pb-1.5 text-[13px] text-text-primary">
          <input
            type="checkbox"
            checked={afa}
            disabled={!canEdit || busy}
            onChange={(e) => {
              setAfa(e.target.checked);
              ment({ plusz_afa: e.target.checked ? "+ÁFA" : null });
            }}
          />
          + ÁFA
        </label>
        <label className="block text-[13px] text-text-secondary">
          Pénznem
          <select
            value={valuta}
            disabled={!canEdit || busy}
            onChange={(e) => {
              setValuta(e.target.value);
              // Forintra visszaállítva az árfolyamnak nincs értelme.
              if (!devizas(e.target.value)) {
                setArfolyamErtek("");
                ment({ penznem: e.target.value, arfolyam: null });
              } else if (arfolyamSzam !== null) {
                ment({ penznem: e.target.value, arfolyam: arfolyamSzam });
              }
            }}
            className="mt-1 w-24 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary disabled:opacity-60"
          >
            {PENZNEMEK.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>
        {devizas(valuta) && (
          <label className="block text-[13px] text-text-secondary">
            Árfolyam (Ft/{valuta})
            <input
              type="text"
              inputMode="decimal"
              value={arfolyamErtek}
              disabled={!canEdit || busy}
              placeholder="Kötelező"
              onChange={(e) => setArfolyamErtek(e.target.value)}
              onBlur={() => {
                if (arfolyamSzam === null || !Number.isFinite(arfolyamSzam)) return;
                if (arfolyamSzam === arfolyam) return;
                ment({ penznem: valuta, arfolyam: arfolyamSzam });
              }}
              className="mt-1 w-28 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary disabled:opacity-60"
            />
          </label>
        )}
        <p className="pb-1.5 text-[13px] text-text-secondary">
          Bruttó: <span className="text-text-primary">{bruttoErtek === null ? "–" : penzzel(bruttoErtek, valuta)}</span>
        </p>
      </div>

      {/* Devizás munkánál a bevétel ETTŐL a számtól függ - ki is írjuk, hogy
          ne csak a szerződésbeli összeg látszódjon. */}
      {devizas(valuta) && (
        <p className="text-[12.5px] text-text-secondary">
          {forintban === null
            ? "Add meg az árfolyamot - enélkül nem tudjuk, mennyi a bevétel forintban."
            : `A bevételek közé ${formatHuf(forintban)} kerül (nettó, ${valuta === "HUF" ? "" : `${arfolyamErtek} Ft/${valuta} árfolyamon`}).`}
        </p>
      )}

      {!ervenyes && <p className="text-[12px] text-text-danger">Ez nem szám.</p>}
      {hiba && <p className="text-[12px] text-text-danger">{hiba}</p>}

      {/* Ha a papíron más összeg áll, azt kiírjuk - de nem írjuk felül
          egyiket sem: a papír azt őrzi, ami RAJTA van. */}
      {papirbolNetto !== null && papirbolNetto !== szam && (
        <p className="text-[12px] text-text-muted">
          A papírokon (TIG / szerződés) {penzzel(papirbolNetto, valuta)} nettó szerepel – a számla és a bevétel
          ezzel számol.
        </p>
      )}
      <p className="text-[12px] text-text-muted">
        Ebből tölti elő magát a szerződés és a TIG, és ez adja a számla összegét is.
      </p>
    </div>
  );
}
