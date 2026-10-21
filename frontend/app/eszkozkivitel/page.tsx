"use client";

import { useEffect, useMemo, useState } from "react";
import { selectColor } from "@/lib/selectColor";

// Ugyanaz az alapértelmezés, mint a lib/authFetch-ben: env nélkül (fejlesztői
// környezet) a lokális backend - élesben a NEXT_PUBLIC_API_URL van beállítva.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Eszkoz = { id: number; nev: string; kategoria: string | null; track_mode: string };
type Ajanlott = Eszkoz & { db: number };
type Tetel = Eszkoz & { kivitt_db: number; visszahozott_db: number };
type Belepes = {
  projekt_nev: string | null;
  forgatas_datuma: string | null;
  forgatas_vege: string | null;
  ervenyes_eddig: string | null;
  teszt: boolean;
  allapot: "kivitel" | "vissza" | "lezart";
  kulso_szoveg: string | null;
  ajanlott: Ajanlott[];
  tetelek: Tetel[];
  eszkozok: Eszkoz[];
};

function datum(value: string | null): string {
  return value ? new Date(value).toLocaleDateString("hu-HU") : "–";
}

/** Publikus (bejelentkezés nélküli) ESZKÖZKIVITELI oldal - a felhasználó
 * kérése szerint FÁZISOKBAN:
 *
 * 1. KIVITEL: a forgatásra kiírt technika súgó + kereső; a "Kivitel
 *    lezárása" gombbal zárul.
 * 2. VISSZAHOZATAL: a kivitt lista már NEM látszik (a backend a kivitt
 *    darabszámokat ki is nullázza a publikus válaszban), így nem lehet
 *    belőle "visszamásolni", mit kellene visszahozottnak írni. Innen
 *    nyitható a PÓT-KIVITEL (újabb kivitel felvezetése): csak hozzáadás,
 *    a korábbi kivitel nélkül.
 * 3. LEZÁRÁS: a visszahozatal lezárásakor megadható (vagy kihagyható) egy
 *    észrevétel az eszközökről/forgatásról.
 *
 * Az "admin" kód mindig él, a teszt-kivitelbe visz, és lezárás után
 * belépéskor tisztán újraindul - a folyamat akárhányszor végigpróbálható. */
export default function EszkozKivitelOldal() {
  const [kod, setKod] = useState("");
  const [adat, setAdat] = useState<Belepes | null>(null);
  const [aktivKod, setAktivKod] = useState("");
  const [hiba, setHiba] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [kereses, setKereses] = useState("");
  //: Pót-kivitel mód a visszahozatal fázisban - a most hozzáadott darabok
  //: KLIENS-oldali számlálója (a szerver a teljes kivittet nem adja vissza).
  const [potKivitel, setPotKivitel] = useState(false);
  const [potDarabok, setPotDarabok] = useState<Map<number, number>>(new Map());
  const [lezarasNyitva, setLezarasNyitva] = useState(false);
  //: A kivitel lezárásakor: a forgatásra KIÍRT, de be nem pakolt technika
  //: listája - ha van ilyen, rákérdezünk, biztos nélkülük indul-e (a
  //: felhasználó kérése). null = nincs nyitva a kérdés.
  const [kiirtHianyzik, setKiirtHianyzik] = useState<Ajanlott[] | null>(null);
  const [eszrevetel, setEszrevetel] = useState("");
  //: Sikeres lezárás után a kezdő (kód) képernyőre esünk vissza, ezzel az
  //: üzenettel (a felhasználó kérése).
  const [kezdoUzenet, setKezdoUzenet] = useState<string | null>(null);
  //: A "nem leltári eszköz" szabad szöveg az aktuális fázishoz.
  const [kulso, setKulso] = useState("");
  //: Művelet-hiba beágyazott sávként (natív alert() helyett, ugyanazért).
  const [muveletHiba, setMuveletHiba] = useState<string | null>(null);

  // A lezárás utáni zöld siker-sáv 5 másodperc után magától eltűnik (a
  // felhasználó kérése).
  useEffect(() => {
    if (!kezdoUzenet) return;
    const idozito = setTimeout(() => setKezdoUzenet(null), 5000);
    return () => clearTimeout(idozito);
  }, [kezdoUzenet]);

  async function belep() {
    if (!kod.trim() || busy) return;
    setBusy(true);
    setHiba(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/public/eszkozkivitel/belepes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ kod: kod.trim() }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? "Nem sikerült belépni.");
        return;
      }
      const valasz: Belepes = await res.json();
      setAdat(valasz);
      setAktivKod(kod.trim());
      setKereses("");
      setPotKivitel(false);
      setPotDarabok(new Map());
      setKulso(valasz.kulso_szoveg ?? "");
      setKezdoUzenet(null);
    } catch {
      setHiba("Hálózati hiba - próbáld újra.");
    } finally {
      setBusy(false);
    }
  }

  async function ment(equipmentId: number, mezok: Record<string, number>) {
    if (!adat) return false;
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/public/eszkozkivitel/${encodeURIComponent(aktivKod)}/tetel`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ equipment_id: equipmentId, ...mezok }),
        },
      );
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setMuveletHiba(detail?.detail ?? "Nem sikerült menteni.");
        return false;
      }
      setAdat({ ...adat, tetelek: await res.json() });
      setMuveletHiba(null);
      return true;
    } catch {
      setMuveletHiba("Hálózati hiba - próbáld újra.");
      return false;
    }
  }

  async function lezar(mit: "kivitel" | "vissza", megjegyzes?: string) {
    if (busy) return;
    setBusy(true);
    try {
      // A "nem leltári eszköz" szöveg biztosan mentve legyen, mielőtt a
      // fázis lezárul (a gombra kattintás megelőzheti a mező blur-mentését).
      await mentKulso();
      const res = await fetch(
        `${API_BASE}/api/v1/public/eszkozkivitel/${encodeURIComponent(aktivKod)}/lezaras`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mit, megjegyzes: megjegyzes || null }),
        },
      );
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setMuveletHiba(detail?.detail ?? "Nem sikerült lezárni.");
        return;
      }
      // Bármelyik lezárás után vissza a kezdő (kód) képernyőre (a
      // felhasználó kérése) - a visszahozatalhoz újra a kóddal kell belépni.
      setAdat(null);
      setKod("");
      setAktivKod("");
      setKereses("");
      setPotKivitel(false);
      setPotDarabok(new Map());
      setLezarasNyitva(false);
      setKiirtHianyzik(null);
      setEszrevetel("");
      setKulso("");
      setMuveletHiba(null);
      setHiba(null);
      setKezdoUzenet(
        mit === "kivitel"
          ? "A kivitel lezárva - jó forgatást! Visszaéréskor ugyanezzel a kóddal írd be, mit hoztál vissza."
          : "A visszahozatal lezárva - köszönjük! Amíg a kód él, ugyanezzel a kóddal még bele tudsz írni.",
      );
    } catch {
      setMuveletHiba("Hálózati hiba - próbáld újra.");
    } finally {
      setBusy(false);
    }
  }

  /** A "nem leltári eszköz" szöveg mentése (elkattintáskor). A fázist a
   * kliens küldi, hogy egy lezárás után beérő mentés is a JÓ mezőbe írjon
   * (lásd a backend kulso_mentes kommentjét). */
  async function mentKulso() {
    if (!adat) return;
    try {
      await fetch(`${API_BASE}/api/v1/public/eszkozkivitel/${encodeURIComponent(aktivKod)}/kulso`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ szoveg: kulso, fazis: adat.allapot === "kivitel" ? "kivitel" : "vissza" }),
      });
    } catch {
      setMuveletHiba("Nem sikerült menteni a szabad szöveget - hálózati hiba.");
    }
  }

  const tetelTerkep = useMemo(
    () => new Map((adat?.tetelek ?? []).map((t) => [t.id, t])),
    [adat?.tetelek],
  );

  /** A kereső találatai KATEGÓRIÁNKÉNT csoportosítva. */
  const talalatok = useMemo(() => {
    if (!adat) return [];
    const keresett = kereses.trim().toLocaleLowerCase("hu-HU");
    if (keresett.length < 2) return [];
    const illik = adat.eszkozok.filter((e) =>
      `${e.nev} ${e.kategoria ?? ""}`.toLocaleLowerCase("hu-HU").includes(keresett),
    );
    const csoportok = new Map<string, Eszkoz[]>();
    for (const e of illik.slice(0, 60)) {
      const kulcs = e.kategoria?.trim() || "Egyéb";
      if (!csoportok.has(kulcs)) csoportok.set(kulcs, []);
      csoportok.get(kulcs)!.push(e);
    }
    return [...csoportok.entries()];
  }, [adat, kereses]);

  // ── 1. képernyő: kód ───────────────────────────────────────────────────────
  if (!adat) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-surface-1 p-6">
        <SugoGomb />
        <div className="w-full max-w-sm text-center">
          <h1 className="text-2xl font-semibold text-text-primary">Eszközkivitel</h1>
          {kezdoUzenet && (
            <p className="mt-3 rounded-[var(--radius-lg)] border border-text-success/40 bg-surface-2 px-3 py-2.5 text-[14px] text-text-success">
              {kezdoUzenet}
            </p>
          )}
          <p className="mt-2 text-[14px] text-text-secondary">
            Írd be a forgatásod 6 jegyű kódját, és add meg, mit viszel ki és mit hozol vissza.
          </p>
          <form
            className="mt-6 space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              void belep();
            }}
          >
            <input
              autoFocus
              value={kod}
              onChange={(e) => setKod(e.target.value)}
              inputMode="numeric"
              placeholder="••••••"
              aria-label="Belépő kód"
              className="w-full rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-4 text-center text-3xl tracking-[0.4em] text-text-primary focus:outline-none"
            />
            <button
              type="submit"
              disabled={busy || !kod.trim()}
              className="w-full rounded-[var(--radius-lg)] bg-text-accent px-4 py-3 text-[16px] font-semibold text-surface-1 disabled:opacity-50"
            >
              {busy ? "Belépés…" : "Belépés"}
            </button>
          </form>
          {hiba && <p className="mt-3 text-[13.5px] text-text-danger">{hiba}</p>}
        </div>
      </main>
    );
  }

  // ── Lezárt kivitel ────────────────────────────────────────────────────────
  if (adat.allapot === "lezart") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-surface-1 p-6">
        <div className="w-full max-w-sm text-center">
          <h1 className="text-xl font-semibold text-text-primary">Ez a kivitel le van zárva</h1>
          <p className="mt-2 text-[14px] text-text-secondary">
            Köszönjük! A kivitel és a visszahozatal rögzítve van - ha mégis módosítani kell, szólj az
            irodának.
          </p>
        </div>
      </main>
    );
  }

  const fazisKivitel = adat.allapot === "kivitel";
  const kivitelLista = adat.tetelek.filter((t) => t.kivitt_db > 0);
  const visszaLista = adat.tetelek.filter((t) => t.visszahozott_db > 0);

  /** Mit tegyen a kereső-találatra kattintás az aktuális fázisban.
   * EGYEDI (asset) eszközből legfeljebb 1 db - a további kattintás nem növel
   * (a felhasználó kérése); a készletesből (stock) annyi, amennyi kell. */
  async function talalatKattintas(e: Eszkoz) {
    const egyedi = e.track_mode !== "stock";
    if (fazisKivitel) {
      const darab = tetelTerkep.get(e.id)?.kivitt_db ?? 0;
      if (egyedi && darab >= 1) return;
      await ment(e.id, { kivitt_db: darab + 1 });
    } else if (potKivitel) {
      if (egyedi && (potDarabok.get(e.id) ?? 0) >= 1) return;
      const ok = await ment(e.id, { kivitt_hozzaadas: 1 });
      if (ok) {
        setPotDarabok((elozo) => {
          const uj = new Map(elozo);
          uj.set(e.id, (uj.get(e.id) ?? 0) + 1);
          return uj;
        });
      }
    } else {
      const darab = tetelTerkep.get(e.id)?.visszahozott_db ?? 0;
      if (egyedi && darab >= 1) return;
      await ment(e.id, { visszahozott_db: darab + 1 });
    }
  }

  // A lépések számozása: kiírt technika nélkül a kereső az 1. lépés.
  const lepesKereso = fazisKivitel && adat.ajanlott.length > 0 ? 2 : 1;
  const lepesLista = lepesKereso + 1;
  const bepakoltKiirt = adat.ajanlott.filter((a) => (tetelTerkep.get(a.id)?.kivitt_db ?? 0) > 0).length;

  /** „Mindet bepakoltam”: a kiírt, még be nem pakolt tételek a kiírt
   * darabszámmal a kivitelbe (egymás után mentve). */
  async function mindetBepakol() {
    if (!adat) return;
    setBusy(true);
    try {
      for (const a of adat.ajanlott) {
        if ((tetelTerkep.get(a.id)?.kivitt_db ?? 0) > 0) continue;
        if (!(await ment(a.id, { kivitt_db: a.db }))) break;
      }
    } finally {
      setBusy(false);
    }
  }

  const keresoSzoveg = fazisKivitel
    ? "Keress eszközt, amit kiviszel…"
    : potKivitel
      ? "Keress eszközt, amit még kiviszel…"
      : "Keress eszközt, amit visszahoztál…";

  return (
    <main className="min-h-screen bg-surface-1 pb-24">
      <SugoGomb />
      {/* Felül extra térköz, amíg a sarokban ülő Súgó gomb a tartalom fölé
          lógna - széles kijelzőn (lg) már elfér mellette. */}
      <div className="mx-auto w-full max-w-3xl px-4 pb-4 pt-16 md:px-8 md:pb-8 lg:pt-8">
        <header className="mb-5">
          {/* NAGY fázis-jelző sáv - egyértelműen látszódjon, hogy épp a
              kivitelt vagy a visszahozatalt írja az ember (a felhasználó
              kérése). */}
          <div
            className={`mb-3 rounded-[var(--radius-lg)] border px-4 py-3 text-center text-[22px] font-bold uppercase tracking-widest ${
              fazisKivitel
                ? "border-text-accent/40 bg-text-accent/10 text-text-accent"
                : "border-text-warning/40 bg-text-warning/10 text-text-warning"
            }`}
          >
            {fazisKivitel ? "Kivitel" : potKivitel ? "Pót-kivitel" : "Visszahozatal"}
          </div>
          <h1 className="text-xl font-semibold text-text-primary">
            {adat.projekt_nev ?? "Forgatás"}
            {adat.teszt && (
              <span className="ml-2 rounded-full bg-surface-3 px-2 py-0.5 text-[12px] text-text-warning">TESZT</span>
            )}
          </h1>
          <p className="mt-1 text-[13px] text-text-secondary">
            Forgatás: {datum(adat.forgatas_datuma)}
            {adat.forgatas_vege && adat.forgatas_vege !== adat.forgatas_datuma ? ` – ${datum(adat.forgatas_vege)}` : ""}
            {adat.ervenyes_eddig && ` · A kód eddig él: ${datum(adat.ervenyes_eddig)}`}
          </p>
        </header>

        {/* RÖVID ÚTMUTATÓ - a felhasználó kérése: a kód beírása után ne
            kelljen kitalálni, mi a kiírt lista, mi a kereső és mi az, ami
            ténylegesen rögzül. Ezért a képernyő SZÁMOZOTT LÉPÉSEKBŐL áll. */}
        <ol className="mb-5 space-y-1 rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-3 text-[13.5px] text-text-secondary">
          {fazisKivitel ? (
            <>
              {adat.ajanlott.length > 0 && (
                <li>
                  <b className="text-text-primary">1.</b> Pipáld ki a kiírt listából, amit tényleg bepakolsz.
                </li>
              )}
              <li>
                <b className="text-text-primary">{lepesKereso}.</b> Ami nincs a kiírt listán, de viszed, keresd meg és add hozzá.
              </li>
              <li>
                <b className="text-text-primary">{lepesLista}.</b> Nézd át lent, mit viszel ki, és nyomd meg a „Kivitel lezárása” gombot.
              </li>
            </>
          ) : potKivitel ? (
            <>
              <li>
                <b className="text-text-primary">1.</b> Keresd meg, amit még kiviszel, és koppints rá - hozzáadódik a kivitelhez.
              </li>
              <li>
                <b className="text-text-primary">2.</b> Ha kész, nyomd meg a „Kész, vissza a visszahozatalhoz” gombot.
              </li>
            </>
          ) : (
            <>
              <li>
                <b className="text-text-primary">1.</b> Keresd meg egyenként, amit visszahoztál, és koppints rá.
              </li>
              <li>
                <b className="text-text-primary">2.</b> Nézd át lent a listádat, és nyomd meg a „Visszahozatal lezárása” gombot.
              </li>
            </>
          )}
        </ol>

        {/* 1. LÉPÉS (csak kivitelnél): a forgatásra KIÍRT technika
            kipipálható listaként - egyértelmű, mi van bepakolva és mi nem. */}
        {fazisKivitel && adat.ajanlott.length > 0 && (
          <Lepes
            szam={1}
            cim="A forgatásra kiírt technika"
            magyarazat="Ezt írta ki az iroda erre a forgatásra. Koppints arra, amit bepakoltál - bekerül a kivitelbe. Ami nem megy, azt hagyd üresen."
            jobbra={
              <span className="text-[13px] tabular-nums text-text-secondary">
                {bepakoltKiirt} / {adat.ajanlott.length} bepakolva
              </span>
            }
          >
            <div className="space-y-1.5">
              {adat.ajanlott.map((a) => {
                const megvan = (tetelTerkep.get(a.id)?.kivitt_db ?? 0) > 0;
                return (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => void ment(a.id, { kivitt_db: megvan ? 0 : a.db })}
                    className={`flex w-full items-center gap-3 rounded-[var(--radius-lg)] border px-3 py-2.5 text-left transition-colors ${
                      megvan
                        ? "border-text-success/50 bg-text-success/10"
                        : "border-border bg-surface-3 hover:border-text-accent/50"
                    }`}
                  >
                    <span
                      aria-hidden
                      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md border text-[14px] font-bold ${
                        megvan ? "border-text-success bg-text-success text-surface-1" : "border-border-strong text-transparent"
                      }`}
                    >
                      ✓
                    </span>
                    <span className="min-w-0 flex-1 break-words text-[14.5px] text-text-primary">{a.nev}</span>
                    {a.db > 1 && <span className="shrink-0 text-[13px] text-text-muted">{a.db} db</span>}
                    {/* Mobilon a pipa elég - a felirat a nevet szorítaná ki. */}
                    <span className={`hidden shrink-0 text-[12.5px] sm:inline ${megvan ? "text-text-success" : "text-text-muted"}`}>
                      {megvan ? "Bepakolva" : "Nincs bepakolva"}
                    </span>
                  </button>
                );
              })}
            </div>
            {bepakoltKiirt < adat.ajanlott.length && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void mindetBepakol()}
                className="mt-3 w-full rounded-[var(--radius)] border border-border px-3 py-2 text-[13.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Mindet bepakoltam
              </button>
            )}
          </Lepes>
        )}

        {/* PÓT-KIVITEL magyarázat. */}
        {!fazisKivitel && potKivitel && (
          <section className="mb-5 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-3">
            <p className="text-[13px] text-text-primary">
              Újabb kivitelt vezetsz fel: amit itt beírsz, HOZZÁADÓDIK a kivitelhez. A korábban beírt
              kivitel itt nem látszik, és nem is módosítható.
            </p>
            <button
              type="button"
              onClick={() => {
                setPotKivitel(false);
                setPotDarabok(new Map());
                setKereses("");
              }}
              className="mt-2 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
            >
              ← Kész, vissza a visszahozatalhoz
            </button>
          </section>
        )}

        {/* KERESŐ LÉPÉS - kategóriánként csoportosított, nagy találat-gombok. */}
        <Lepes
          szam={lepesKereso}
          cim={
            fazisKivitel
              ? adat.ajanlott.length > 0
                ? "Más is megy? Keresd meg"
                : "Keresd meg, amit kiviszel"
              : potKivitel
                ? "Keresd meg, amit még kiviszel"
                : "Keresd meg, amit visszahoztál"
          }
          magyarazat="Írj be legalább 2 betűt a nevéből (pl. „akku”, „Sony”), majd koppints a találatra - bekerül a lenti listába. Készletes eszközt többször is koppinthatsz (darabszám)."
        >
          <input
            value={kereses}
            onChange={(e) => setKereses(e.target.value)}
            placeholder={keresoSzoveg}
            aria-label="Eszköz keresése"
            className="w-full rounded-[var(--radius-lg)] border border-border bg-surface-3 px-4 py-3 text-[16px] text-text-primary focus:outline-none"
          />
          {kereses.trim().length === 1 && (
            <p className="mt-2 text-[12.5px] text-text-muted">Írj még legalább egy betűt…</p>
          )}
          {kereses.trim().length >= 2 && (
            <div className="mt-2 space-y-3">
              {talalatok.length === 0 && (
                <p className="text-[13px] text-text-muted">
                  Nincs ilyen eszköz a leltárban. Ha bérelt vagy külsős cucc, írd lent a „Nem leltári eszköz” mezőbe.
                </p>
              )}
              {talalatok.map(([kategoria, elemek]) => {
                const c = selectColor(kategoria);
                return (
                  <div key={kategoria}>
                    <p
                      className="mb-1.5 inline-block rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide"
                      style={{ background: c.bg, color: c.text }}
                    >
                      {kategoria}
                    </p>
                    <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                      {elemek.map((e) => {
                        const darab = fazisKivitel
                          ? (tetelTerkep.get(e.id)?.kivitt_db ?? 0)
                          : potKivitel
                            ? (potDarabok.get(e.id) ?? 0)
                            : (tetelTerkep.get(e.id)?.visszahozott_db ?? 0);
                        const egyediMarBent = e.track_mode !== "stock" && darab >= 1;
                        return (
                          <button
                            key={e.id}
                            type="button"
                            onClick={() => void talalatKattintas(e)}
                            className={`flex items-center justify-between rounded-[var(--radius)] border px-3 py-2.5 text-left text-[14px] text-text-primary ${
                              darab > 0
                                ? "border-text-success/50 bg-text-success/10"
                                : "border-border bg-surface-3 hover:border-text-accent/50"
                            }`}
                          >
                            <span className="min-w-0 break-words">{e.nev}</span>
                            <span
                              className={`ml-2 shrink-0 text-[12.5px] ${darab > 0 ? "text-text-success" : "text-text-accent"}`}
                            >
                              {egyediMarBent ? "✓ a listádban" : darab > 0 ? `✓ ${darab} db · +1` : "+ Hozzáad"}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Lepes>

        {/* A LISTÁM az aktuális fázisban - ez rögzül. */}
        {fazisKivitel && (
          <Lepes
            szam={lepesLista}
            cim="Amit kiviszel - ez kerül rögzítésre"
            magyarazat="Ide kerül minden, amit fent kipipáltál vagy hozzáadtál. A − / + gombbal a darabszám javítható."
          >
            <SajatLista
              ures="Még üres - pipálj ki valamit a kiírt listából, vagy keress rá fent."
              sorok={kivitelLista.map((t) => ({ ...t, darab: t.kivitt_db }))}
              valtoztat={(id, darab) => void ment(id, { kivitt_db: darab })}
            />
          </Lepes>
        )}
        {!fazisKivitel && !potKivitel && (
          <Lepes
            szam={2}
            cim="Amit visszahoztál - ez kerül rögzítésre"
            magyarazat="A − / + gombbal a darabszám javítható."
          >
            <SajatLista
              ures="Még üres - keress rá fent arra, amit visszahoztál."
              sorok={visszaLista.map((t) => ({ ...t, darab: t.visszahozott_db }))}
              valtoztat={(id, darab) => void ment(id, { visszahozott_db: darab })}
            />
          </Lepes>
        )}
        {!fazisKivitel && potKivitel && (
          <Lepes szam={2} cim="Amit most még kiviszel (pót-kivitel)" magyarazat="Ez hozzáadódik a korábbi kivitelhez.">
            <SajatLista
              ures="Még üres - keress rá fent."
              sorok={[...potDarabok.entries()]
                .filter(([, darab]) => darab > 0)
                .map(([id, darab]) => {
                  const e = adat.eszkozok.find((x) => x.id === id);
                  return {
                    id,
                    nev: e?.nev ?? `#${id}`,
                    kategoria: e?.kategoria ?? null,
                    track_mode: e?.track_mode,
                    darab,
                  };
                })}
              // Pót-kivitelnél csak NÖVELNI lehet (a csökkentés a korábbi
              // kivitelt is vissza tudná írni) - a "-" gomb ezért nincs.
              csakNoveles
              valtoztat={(id) => {
                void ment(id, { kivitt_hozzaadas: 1 }).then((ok) => {
                  if (ok) {
                    setPotDarabok((elozo) => {
                      const uj = new Map(elozo);
                      uj.set(id, (uj.get(id) ?? 0) + 1);
                      return uj;
                    });
                  }
                });
              }}
            />
          </Lepes>
        )}

        {/* NEM LELTÁRI ESZKÖZ (bérelt, külsős cucc) - szabad szöveg, az
            aktuális fázishoz mentve (a felhasználó kérése). */}
        <section className="mt-5">
          <p className="mb-1.5 text-[13px] font-medium text-text-primary">
            {fazisKivitel || potKivitel
              ? "Nem leltári eszköz kivitele (bérelt, külsős cucc)"
              : "Nem leltári eszköz visszahozatala (bérelt, külsős cucc)"}
          </p>
          <textarea
            value={kulso}
            onChange={(e) => setKulso(e.target.value)}
            onBlur={() => void mentKulso()}
            rows={2}
            placeholder="Pl. 2 db bérelt robotlámpa a Rentaltól…"
            className="w-full rounded-[var(--radius-lg)] border border-border bg-surface-2 px-3 py-2.5 text-[14px] text-text-primary focus:outline-none"
          />
        </section>

        {/* FÁZIS-GOMBOK - a lezárás EGY gombnyomás, azonnal (a felhasználó
            kérése). */}
        {muveletHiba && (
          <p className="mt-6 rounded-[var(--radius)] border border-text-danger/40 bg-surface-2 px-3 py-2 text-[13.5px] text-text-danger">
            {muveletHiba}
          </p>
        )}
        <div className="mt-8 space-y-2">
          {fazisKivitel ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                // Ha a forgatásra kiírt technikából valami nincs bepakolva,
                // előbb rákérdezünk - csak megerősítés után zárunk le.
                const hianyzik = adat.ajanlott.filter(
                  (a) => (tetelTerkep.get(a.id)?.kivitt_db ?? 0) === 0,
                );
                if (hianyzik.length > 0) setKiirtHianyzik(hianyzik);
                else void lezar("kivitel");
              }}
              className="w-full rounded-[var(--radius-lg)] bg-text-accent px-4 py-3.5 text-[16px] font-semibold text-surface-1 disabled:opacity-50"
            >
              {busy ? "Lezárás…" : "Kivitel lezárása – indulhat a forgatás"}
            </button>
          ) : (
            !potKivitel && (
              <>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => setLezarasNyitva(true)}
                  className="w-full rounded-[var(--radius-lg)] bg-text-accent px-4 py-3.5 text-[16px] font-semibold text-surface-1 disabled:opacity-50"
                >
                  Visszahozatal lezárása
                </button>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setPotKivitel(true);
                    setKereses("");
                  }}
                  className="w-full rounded-[var(--radius-lg)] border border-border px-4 py-3 text-[14.5px] text-text-secondary hover:bg-surface-2"
                >
                  Újabb kivitel felvezetése
                </button>
              </>
            )
          )}
        </div>

        <footer className="mt-6 text-center text-[12px] text-text-muted">Minden beírás azonnal mentődik.</footer>
      </div>

      {/* KIÍRT-DE-KIMARADT ABLAK: a kivitel lezárása előtt rákérdezünk a
          forgatásra kiírt, de be nem pakolt technikára (a felhasználó
          kérése). */}
      {kiirtHianyzik && (
        <div
          className="fixed inset-0 z-[300] flex items-center justify-center bg-black/60 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setKiirtHianyzik(null);
          }}
        >
          <div className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 p-4 shadow-xl">
            <h2 className="text-[16px] font-semibold text-text-primary">
              Ki van írva, de nincs a listádban
            </h2>
            <p className="mt-1 text-[13.5px] text-text-secondary">
              Ezek ki lettek írva erre a forgatásra, de nem raktad be a kivitelbe. Biztos nem akarod
              elvinni őket?
            </p>
            <ul className="mt-3 max-h-56 space-y-1.5 overflow-y-auto">
              {kiirtHianyzik.map((a) => {
                const c = selectColor(a.kategoria?.trim() || a.nev);
                return (
                  <li
                    key={a.id}
                    className="flex items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2 text-[14px] text-text-primary"
                  >
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: c.text }} />
                    <span className="min-w-0 flex-1 truncate">{a.nev}</span>
                    {a.db > 1 && <span className="shrink-0 text-[13px] text-text-muted">{a.db} db</span>}
                  </li>
                );
              })}
            </ul>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setKiirtHianyzik(null)}
                className="rounded-[var(--radius)] bg-text-accent px-3 py-2 text-[13.5px] font-semibold text-surface-1"
              >
                Visszamegyek, még pakolok
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void lezar("kivitel")}
                className="rounded-[var(--radius)] border border-border px-3 py-2 text-[13.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Biztos nem viszem – lezárás
              </button>
            </div>
          </div>
        </div>
      )}

      {/* LEZÁRÁS-ABLAK: észrevétel megadható vagy kihagyható. */}
      {lezarasNyitva && (
        <div
          className="fixed inset-0 z-[300] flex items-center justify-center bg-black/60 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setLezarasNyitva(false);
          }}
        >
          <div className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 p-4 shadow-xl">
            <h2 className="text-[16px] font-semibold text-text-primary">Mielőtt lezárod…</h2>
            <p className="mt-1 text-[13.5px] text-text-secondary">
              Volt az eszközökkel vagy a forgatással kapcsolatban észrevétel, vagy bármi, amiről jó, ha
              tudunk? (Pl. sérült eszköz, hiányzó tartozék.)
            </p>
            <textarea
              autoFocus
              value={eszrevetel}
              onChange={(e) => setEszrevetel(e.target.value)}
              rows={4}
              placeholder="Írd ide, ha van…"
              className="mt-3 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2 text-[14px] text-text-primary focus:outline-none"
            />
            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setLezarasNyitva(false)}
                className="rounded-[var(--radius)] border border-border px-3 py-2 text-[13.5px] text-text-secondary hover:bg-surface-3"
              >
                Mégse
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void lezar("vissza")}
                className="rounded-[var(--radius)] border border-border px-3 py-2 text-[13.5px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Nincs észrevétel – lezárás
              </button>
              <button
                type="button"
                disabled={busy || !eszrevetel.trim()}
                onClick={() => void lezar("vissza", eszrevetel)}
                className="rounded-[var(--radius)] bg-text-accent px-3 py-2 text-[13.5px] font-semibold text-surface-1 disabled:opacity-50"
              >
                Lezárás észrevétellel
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

/** Súgó gomb a jobb felső sarokban + felugró ablak, ami pontosan
 * elmagyarázza, hogyan működik a rendszer (a felhasználó kérése). Ugyanez a
 * gomb van a kezdő (kód) képernyőn, a kivitelnél és a visszahozatalnál is. */
function SugoGomb() {
  const [nyitva, setNyitva] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setNyitva(true)}
        aria-label="Súgó"
        className="fixed right-4 top-4 z-[200] rounded-full border border-border bg-surface-2 px-4 py-2 text-[14px] font-semibold text-text-secondary shadow-md hover:bg-surface-3"
      >
        Súgó
      </button>
      {nyitva && (
        <div
          className="fixed inset-0 z-[400] flex items-center justify-center bg-black/60 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setNyitva(false);
          }}
        >
          <div className="flex max-h-[85vh] w-full max-w-lg flex-col rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <h2 className="text-[16px] font-semibold text-text-primary">Hogyan működik?</h2>
              <button
                type="button"
                onClick={() => setNyitva(false)}
                aria-label="Bezárás"
                className="rounded-full border border-border px-3 py-1 text-[13px] text-text-secondary hover:bg-surface-3"
              >
                Bezárás
              </button>
            </div>
            <div className="space-y-4 overflow-y-auto px-4 py-4 text-[14px] text-text-secondary">
              <p>
                Ezen az oldalon írod fel, milyen technikát viszel ki egy forgatásra, és mit hozol
                vissza utána. Így mindig tudjuk, mi van kint, és mi hiányzik.
              </p>
              <div>
                <p className="font-semibold text-text-primary">Belépés</p>
                <p className="mt-1">
                  Minden forgatásnak saját 6 jegyű kódja van - ezt az irodától kapod. A kód a
                  forgatás utolsó napja után még 48 óráig él, utána lejár.
                </p>
              </div>
              <div>
                <p className="font-semibold text-text-primary">1. Kivitel (pakolásnál)</p>
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  <li>
                    <b>1. lépés:</b> a forgatásra kiírt technika listája. Koppints arra, amit
                    bepakoltál - zöld pipát kap, és bekerül a kivitelbe. Ha mindent viszel, a
                    „Mindet bepakoltam” gomb egyszerre kipipálja.
                  </li>
                  <li>
                    <b>2. lépés:</b> ha olyat is viszel, ami nincs kiírva, a keresőbe írd be a
                    nevéből legalább 2 betűt, és koppints a találatra.
                  </li>
                  <li>
                    <b>3. lépés:</b> lent látod, mi kerül rögzítésre - itt a darabszám is
                    javítható.
                  </li>
                  <li>Készletes eszközből több darabot is vihetsz, egyediből legfeljebb egyet.</li>
                  <li>
                    Ha bérelt vagy más, nem leltári cucc is megy, írd be a szabad szövegmezőbe.
                  </li>
                  <li>
                    Ha kész vagy, nyomd meg a &quot;Kivitel lezárása&quot; gombot. Ha kiírt technika
                    maradt ki, az oldal rákérdez, biztos nélküle indulsz-e.
                  </li>
                </ul>
              </div>
              <div>
                <p className="font-semibold text-text-primary">2. Visszahozatal (visszaéréskor)</p>
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  <li>Ugyanazzal a kóddal lépsz be, és beírod, mit hoztál vissza.</li>
                  <li>
                    A kivitelkor beírt lista itt szándékosan nem látszik - fejből (vagy a pakolás
                    alapján) írd be, mi jött vissza.
                  </li>
                  <li>
                    Ha a forgatás közben még vittél ki valamit, az &quot;Újabb kivitel
                    felvezetése&quot; gombbal tudod hozzáadni.
                  </li>
                  <li>
                    A lezárásnál írhatsz észrevételt (pl. sérült eszköz, hiányzó tartozék), de ki is
                    hagyhatod.
                  </li>
                  <li>
                    Amíg a kód él, a lezárt visszahozatalba is vissza tudsz lépni ugyanazzal a
                    kóddal, és még bele tudsz írni.
                  </li>
                </ul>
              </div>
              <p>
                Minden beírás azonnal mentődik, külön menteni nem kell. Ami nem jött vissza, azt az
                iroda látja - ha bármi gond van, szólj nekik.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/** Az aktuális fázis saját listája: név + darabszám, −/+ gombokkal (a
 * pót-kivitelnél csak +, lásd a hívót). */
function SajatLista({
  ures,
  sorok,
  valtoztat,
  csakNoveles = false,
}: {
  ures: string;
  sorok: { id: number; nev: string; kategoria: string | null; track_mode?: string; darab: number }[];
  valtoztat: (id: number, darab: number) => void;
  csakNoveles?: boolean;
}) {
  return (
    <div>
      {sorok.length > 0 && <p className="mb-2 text-[12.5px] text-text-muted">{sorok.length} tétel</p>}
      {sorok.length === 0 ? (
        <p className="rounded-[var(--radius-lg)] border border-dashed border-border p-4 text-[13px] text-text-muted">
          {ures}
        </p>
      ) : (
        <div className="space-y-1.5">
          {sorok.map((t) => {
            const c = selectColor(t.kategoria?.trim() || t.nev);
            return (
              <div
                key={t.id}
                className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-border bg-surface-2 px-3 py-2.5"
              >
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: c.text }} />
                <span className="min-w-0 flex-1 break-words text-[14.5px] text-text-primary">{t.nev}</span>
                <div className="flex shrink-0 items-center gap-2">
                  {!csakNoveles && (
                    <button
                      type="button"
                      aria-label="Kevesebb"
                      onClick={() => valtoztat(t.id, t.darab - 1)}
                      className="h-9 w-9 rounded-full border border-border text-[18px] text-text-secondary hover:bg-surface-3"
                    >
                      −
                    </button>
                  )}
                  <span className="w-10 text-center text-[15px] font-semibold tabular-nums text-text-primary">
                    {t.darab}
                  </span>
                  <button
                    type="button"
                    aria-label="Több"
                    // Egyedi (asset) eszközből legfeljebb 1 db (a felhasználó
                    // kérése) - készletesből bármennyi.
                    disabled={t.track_mode !== "stock" && t.darab >= 1}
                    onClick={() => valtoztat(t.id, t.darab + 1)}
                    className="h-9 w-9 rounded-full border border-border text-[18px] text-text-secondary hover:bg-surface-3 disabled:opacity-30"
                  >
                    +
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Egy számozott lépés kártyája (a felhasználó kérése: a képernyő legyen
 * egyértelmű - mindenhol látszódjon, melyik lépésnél tart, és mit kell
 * csinálni). */
function Lepes({
  szam,
  cim,
  magyarazat,
  jobbra,
  children,
}: {
  szam: number;
  cim: string;
  magyarazat?: string;
  jobbra?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-5 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-3 sm:p-4">
      <div className="mb-2 flex items-start gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-text-accent text-[14px] font-bold text-surface-1">
          {szam}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline justify-between gap-x-3">
            <h2 className="text-[15.5px] font-semibold text-text-primary">{cim}</h2>
            {jobbra}
          </div>
          {magyarazat && <p className="mt-0.5 text-[12.5px] leading-snug text-text-muted">{magyarazat}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}
