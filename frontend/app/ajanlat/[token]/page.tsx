"use client";

/** A KÜLSŐS SZEMÉLYES JELENTKEZÉSI OLDALA - a meghívó e-mail "Érdekel,
 * jelentkezem" gombja ide hoz (publikus, tokenes útvonal: bejelentkezés
 * nélkül működik, lásd middleware PUBLIC_PATHS).
 *
 * ÁRAT NEM KÉRÜNK (a felhasználó kérése): a külsős csak azt jelzi, hogy
 * érdekli a feladat és ráér - a díjazásról a kiválasztottal a rendszeren
 * kívül egyeznek meg. A külsős látja a feladat adatait, ÉLŐ visszaszámlálót
 * a határidőig; a jelentkezését a határidőig módosíthatja és visszavonhatja.
 * Mások nevét vagy a jelentkezők számát nem látja. A határidőt a SZERVER
 * ellenőrzi - lejárat után egy nyitva felejtett űrlap sem tud beküldeni. */

import { use, useEffect, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type SajatJelentkezes = {
  megjegyzes: string | null;
  vallalja: boolean;
  bekuldve: string | null;
  modositva: string | null;
  visszavonva: boolean;
};

type Adatok = {
  projekt_nev: string;
  munkakor: string;
  leiras: string | null;
  helyszin: string | null;
  munkavegzes_idopont: string | null;
  teljesitesi_hatarido: string | null;
  valaszadasi_hatarido_szoveg: string;
  hatralevo_mp: number;
  lejart: boolean;
  lezarult: boolean;
  sajat_ajanlat: SajatJelentkezes | null;
};

function hatralevoSzoveg(mp: number): string {
  if (mp <= 0) return "lejárt";
  const nap = Math.floor(mp / 86400);
  const ora = Math.floor((mp % 86400) / 3600);
  const perc = Math.floor((mp % 3600) / 60);
  const s = Math.floor(mp % 60);
  const darabok: string[] = [];
  if (nap) darabok.push(`${nap} nap`);
  if (ora || nap) darabok.push(`${ora} óra`);
  darabok.push(`${perc} perc`);
  if (!nap) darabok.push(`${s} másodperc`);
  return darabok.join(" ");
}

export default function AjanlatOldal({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [adat, setAdat] = useState<Adatok | null>(null);
  const [betoltesHiba, setBetoltesHiba] = useState<string | null>(null);
  // Élő visszaszámláló: a SZERVER által mondott hátralévő időből indul (nem a
  // látogató órájából), és másodpercenként fogy.
  const lejaratRef = useRef<number | null>(null);
  const [hatralevoMp, setHatralevoMp] = useState<number | null>(null);

  const [megjegyzes, setMegjegyzes] = useState("");
  const [vallalja, setVallalja] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<{ hiba: boolean; szoveg: string } | null>(null);
  const [szerkesztes, setSzerkesztes] = useState(false);
  const [visszavonasKerdes, setVisszavonasKerdes] = useState(false);

  function feldolgoz(d: Adatok) {
    setAdat(d);
    lejaratRef.current = Date.now() + d.hatralevo_mp * 1000;
    setHatralevoMp(d.hatralevo_mp);
    if (d.sajat_ajanlat && !d.sajat_ajanlat.visszavonva && d.sajat_ajanlat.vallalja) {
      setMegjegyzes(d.sajat_ajanlat.megjegyzes ?? "");
      setVallalja(true);
    }
  }

  useEffect(() => {
    fetch(`${API_BASE}/api/v1/public/ajanlat/${token}`)
      .then(async (res) => {
        if (!res.ok) {
          const d = await res.json().catch(() => null);
          throw new Error(d?.detail ?? "Ez a jelentkezési link nem érvényes.");
        }
        return res.json();
      })
      .then((d: Adatok) => feldolgoz(d))
      .catch((err) => setBetoltesHiba(err instanceof Error ? err.message : String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    const idozito = setInterval(() => {
      if (lejaratRef.current === null) return;
      setHatralevoMp(Math.max(0, Math.round((lejaratRef.current - Date.now()) / 1000)));
    }, 1000);
    return () => clearInterval(idozito);
  }, []);

  async function bekuldes() {
    setUzenet(null);
    if (!vallalja) {
      setUzenet({ hiba: true, szoveg: "A jelentkezéshez erősítsd meg, hogy érdekel a feladat, és a megadott időpontban ráérsz." });
      return;
    }
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/public/ajanlat/${token}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ megjegyzes: megjegyzes.trim() || null, vallalja: true }),
      });
      const d = await res.json().catch(() => null);
      if (!res.ok) {
        setUzenet({ hiba: true, szoveg: d?.detail ?? `Hiba (${res.status})` });
        if (res.status === 410 && adat) setAdat({ ...adat, lejart: true });
        return;
      }
      feldolgoz(d as Adatok);
      setSzerkesztes(false);
      setUzenet({
        hiba: false,
        szoveg:
          "Köszönjük, megkaptuk a jelentkezésedet! A határidő lejárta után választunk, és e-mailben értesítünk az eredményről.",
      });
    } catch (err) {
      setUzenet({ hiba: true, szoveg: `Hálózati hiba: ${err}` });
    } finally {
      setBusy(false);
    }
  }

  /** "Sajnos nem érek rá" (a felhasználó kérése): kifejezett lemondás - a
   * határidőig meggondolható, és az eredményről már nem jön külön levél. */
  async function nemErekRa() {
    setBusy(true);
    setUzenet(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/public/ajanlat/${token}/nem-erek-ra`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ megjegyzes: megjegyzes.trim() || null }),
      });
      const d = await res.json().catch(() => null);
      if (!res.ok) {
        setUzenet({ hiba: true, szoveg: d?.detail ?? `Hiba (${res.status})` });
        return;
      }
      feldolgoz(d as Adatok);
      setSzerkesztes(false);
      setVallalja(false);
      setUzenet({
        hiba: false,
        szoveg: "Köszönjük a visszajelzést! Jelezted, hogy most nem érsz rá. Ha meggondolod magad, a határidőig még jelentkezhetsz.",
      });
    } catch (err) {
      setUzenet({ hiba: true, szoveg: `Hálózati hiba: ${err}` });
    } finally {
      setBusy(false);
    }
  }

  async function visszavonas() {
    setBusy(true);
    setUzenet(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/public/ajanlat/${token}`, { method: "DELETE" });
      const d = await res.json().catch(() => null);
      if (!res.ok) {
        setUzenet({ hiba: true, szoveg: d?.detail ?? `Hiba (${res.status})` });
        return;
      }
      feldolgoz(d as Adatok);
      setVisszavonasKerdes(false);
      setSzerkesztes(false);
      setMegjegyzes("");
      setVallalja(false);
      setUzenet({ hiba: false, szoveg: "A jelentkezésedet visszavontad. A határidőig bármikor jelentkezhetsz újra." });
    } catch (err) {
      setUzenet({ hiba: true, szoveg: `Hálózati hiba: ${err}` });
    } finally {
      setBusy(false);
    }
  }

  if (betoltesHiba) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <p className="max-w-md text-center text-[14px] text-text-secondary">{betoltesHiba}</p>
      </div>
    );
  }
  if (!adat) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <p className="text-[14px] text-text-muted">Betöltés…</p>
      </div>
    );
  }

  const lejart = adat.lejart || (hatralevoMp !== null && hatralevoMp <= 0);
  const elo = adat.sajat_ajanlat && !adat.sajat_ajanlat.visszavonva ? adat.sajat_ajanlat : null;
  const elozo = elo && elo.vallalja ? elo : null;
  const lemondta = elo !== null && !elo.vallalja;
  const beviteli =
    "w-full rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2 text-[14px] text-text-primary focus:outline-none focus:ring-1 focus:ring-border-strong";

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-8">
      <div className="rounded-[var(--radius-xl)] border border-border bg-surface-1 p-6 md:p-8">
        <p className="text-[12px] font-medium uppercase tracking-wide text-text-muted">Munkafelajánlás</p>
        <h1 className="mt-1 text-[20px] font-semibold text-text-primary">
          {adat.projekt_nev} <span className="text-text-secondary">/ {adat.munkakor}</span>
        </h1>

        <div className="mt-4 space-y-1.5 text-[13.5px]">
          {adat.leiras && <p><span className="text-text-muted">Feladat:</span> <span className="text-text-secondary">{adat.leiras}</span></p>}
          {adat.munkavegzes_idopont && <p><span className="text-text-muted">A munkavégzés várható időpontja:</span> <span className="text-text-secondary">{adat.munkavegzes_idopont}</span></p>}
          {adat.helyszin && <p><span className="text-text-muted">Helyszín:</span> <span className="text-text-secondary">{adat.helyszin}</span></p>}
          {adat.teljesitesi_hatarido && <p><span className="text-text-muted">Teljesítési határidő:</span> <span className="text-text-secondary">{adat.teljesitesi_hatarido}</span></p>}
          <p><span className="text-text-muted">Jelentkezési határidő:</span> <span className="font-medium text-text-primary">{adat.valaszadasi_hatarido_szoveg}</span> <span className="text-text-muted">(magyar idő szerint)</span></p>
        </div>

        {/* Élő visszaszámláló / lezárt állapot */}
        {adat.lezarult ? (
          <p className="mt-4 rounded-[var(--radius)] bg-surface-3 px-3 py-2.5 text-[13.5px] text-text-secondary">
            Ez a munkafelajánlás lezárult. Ha jelentkeztél, az eredményről e-mailben értesítünk.
          </p>
        ) : lejart ? (
          <p className="mt-4 rounded-[var(--radius)] bg-surface-3 px-3 py-2.5 text-[13.5px] text-text-secondary">
            A jelentkezés lezárult. A kiválasztás folyamatban van, az eredményről külön értesítünk.
          </p>
        ) : (
          <div className="mt-4 rounded-[var(--radius)] bg-bg-accent px-3 py-2.5">
            <p className="text-[14px] font-medium text-text-accent">
              Még {hatralevoSzoveg(hatralevoMp ?? adat.hatralevo_mp)} van a jelentkezésre.
            </p>
            <p className="mt-0.5 text-[12.5px] text-text-secondary">
              A kiválasztás a jelentkezési határidő lejárta után történik. Az eredményről e-mailben értesítünk -
              a jelentkezés még nem jelent megbízást.
            </p>
          </div>
        )}

        {uzenet && (
          <p className={`mt-4 rounded-[var(--radius)] px-3 py-2.5 text-[13.5px] ${uzenet.hiba ? "bg-bg-danger text-text-danger" : "bg-bg-success text-text-success"}`}>
            {uzenet.szoveg}
          </p>
        )}

        {/* A saját jelentkezés */}
        {elozo && !szerkesztes && !adat.lezarult && (
          <div className="mt-5 rounded-[var(--radius)] border border-border bg-surface-2 p-4">
            <p className="text-[13px] font-medium text-text-primary">Jelentkeztél erre a feladatra</p>
            <p className="mt-1 text-[13.5px] text-text-success">Jelezted, hogy érdekel és ráérsz. ✓</p>
            {elozo.megjegyzes && <p className="mt-1 text-[13px] text-text-secondary">Megjegyzésed: {elozo.megjegyzes}</p>}
            {!lejart && (
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" onClick={() => { setSzerkesztes(true); setUzenet(null); }} className="btn btn-primary">
                  Megjegyzés módosítása
                </button>
                {visszavonasKerdes ? (
                  <>
                    <button type="button" disabled={busy} onClick={() => void visszavonas()} className="rounded-[var(--radius)] border border-text-danger px-3 py-1.5 text-[13px] text-text-danger disabled:opacity-50">
                      {busy ? "Visszavonás…" : "Visszavonás megerősítése"}
                    </button>
                    <button type="button" onClick={() => setVisszavonasKerdes(false)} className="text-[13px] text-text-muted">Mégse</button>
                  </>
                ) : (
                  <button type="button" onClick={() => setVisszavonasKerdes(true)} className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:text-text-danger">
                    Jelentkezés visszavonása
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* "Sajnos nem érek rá" - a lemondott állapot */}
        {lemondta && !szerkesztes && !adat.lezarult && (
          <div className="mt-5 rounded-[var(--radius)] border border-border bg-surface-2 p-4">
            <p className="text-[13px] font-medium text-text-primary">Jelezted: sajnos nem érsz rá erre a feladatra.</p>
            {elo?.megjegyzes && <p className="mt-1 text-[13px] text-text-secondary">Megjegyzésed: {elo.megjegyzes}</p>}
            {!lejart && (
              <button
                type="button"
                onClick={() => { setSzerkesztes(true); setUzenet(null); }}
                className="btn btn-primary mt-3"
              >
                Mégis jelentkezem
              </button>
            )}
          </div>
        )}

        {/* Jelentkezési űrlap - ár nélkül */}
        {!adat.lezarult && !lejart && (szerkesztes || (!elozo && !lemondta)) && (
          <div className="mt-5 space-y-4">
            <label className="block text-[12.5px] text-text-muted">
              Megjegyzés (nem kötelező - pl. mikor vagy elérhető, mire figyeljünk)
              <textarea value={megjegyzes} onChange={(e) => setMegjegyzes(e.target.value)} rows={3} className={beviteli} />
            </label>
            <label className="flex cursor-pointer items-start gap-2 text-[13.5px] text-text-secondary">
              <input type="checkbox" checked={vallalja} onChange={(e) => setVallalja(e.target.checked)} className="mt-0.5" />
              Megerősítem, hogy érdekel a feladat, és a megadott időpontban ráérek.
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="button" disabled={busy} onClick={() => void bekuldes()} className="btn btn-primary disabled:opacity-50">
                {busy ? "Küldés…" : "Jelentkezem"}
              </button>
              {/* Kifejezett lemondás (a felhasználó kérése) - ehhez nem kell
                  a megerősítő pipa, hiszen épp azt jelzi, hogy NEM vállalja. */}
              <button
                type="button"
                disabled={busy}
                onClick={() => void nemErekRa()}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Sajnos nem érek rá
              </button>
              {szerkesztes && (
                <button type="button" onClick={() => setSzerkesztes(false)} className="text-[13px] text-text-muted hover:text-text-primary">
                  Mégse
                </button>
              )}
            </div>
          </div>
        )}
      </div>
      <p className="mt-4 text-center text-[11.5px] text-text-muted">HYPE OS – személyre szóló jelentkezési oldal</p>
    </div>
  );
}
