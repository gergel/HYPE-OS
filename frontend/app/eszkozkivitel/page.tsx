"use client";

import { useMemo, useState } from "react";
import { selectColor } from "@/lib/selectColor";

// Ugyanaz az alapértelmezés, mint a lib/authFetch-ben: env nélkül (fejlesztői
// környezet) a lokális backend - élesben a NEXT_PUBLIC_API_URL van beállítva.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Eszkoz = { id: number; nev: string; kategoria: string | null };
type Ajanlott = Eszkoz & { db: number };
type Tetel = Eszkoz & { kivitt_db: number; visszahozott_db: number };
type Belepes = {
  projekt_nev: string | null;
  forgatas_datuma: string | null;
  forgatas_vege: string | null;
  ervenyes_eddig: string | null;
  teszt: boolean;
  ajanlott: Ajanlott[];
  tetelek: Tetel[];
  eszkozok: Eszkoz[];
};

function datum(value: string | null): string {
  return value ? new Date(value).toLocaleDateString("hu-HU") : "–";
}

/** Publikus (bejelentkezés nélküli) ESZKÖZKIVITELI oldal - a felhasználó
 * kérése: a forgatásra kimenő ember egy 6 jegyű kóddal belép, és beírja,
 * pontosan mit visz ki (a forgatásra kiírt technika csak súgó - mást is
 * vihet), majd visszaérve azt, hogy mit hozott vissza (ott már súgó nélkül).
 * A hiány - mi nem jött vissza - szándékosan NEM itt, hanem a bejelentkezett
 * kezelő oldalon látszik (/eszkozkivitelek).
 *
 * Az "admin" kód mindig él, és egy teszt-kivitelbe lép be. A keresés a
 * diszpós listánál átláthatóbb: kategóriánként csoportosított, színezett,
 * nagy találat-gombok (a felhasználó kérése). */
export default function EszkozKivitelOldal() {
  const [kod, setKod] = useState("");
  const [adat, setAdat] = useState<Belepes | null>(null);
  const [aktivKod, setAktivKod] = useState("");
  const [hiba, setHiba] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mod, setMod] = useState<"kivitel" | "vissza">("kivitel");
  const [kereses, setKereses] = useState("");

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
      setAdat(await res.json());
      setAktivKod(kod.trim());
      setKereses("");
    } catch {
      setHiba("Hálózati hiba - próbáld újra.");
    } finally {
      setBusy(false);
    }
  }

  /** Egy eszköz darabszámának mentése - a szerver a teljes tétel-listát adja
   * vissza, így a képernyő mindig a valós állapotot mutatja. */
  async function ment(equipmentId: number, mezo: "kivitt_db" | "visszahozott_db", darab: number) {
    if (!adat) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/public/eszkozkivitel/${encodeURIComponent(aktivKod)}/tetel`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ equipment_id: equipmentId, [mezo]: darab }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(detail?.detail ?? "Nem sikerült menteni.");
        return;
      }
      setAdat({ ...adat, tetelek: await res.json() });
    } catch {
      alert("Hálózati hiba - próbáld újra.");
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

  const aktualisMezo = mod === "kivitel" ? "kivitt_db" : "visszahozott_db";
  const listam = (adat?.tetelek ?? []).filter((t) =>
    mod === "kivitel" ? t.kivitt_db > 0 : t.visszahozott_db > 0,
  );

  // ── 1. képernyő: kód ───────────────────────────────────────────────────────
  if (!adat) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-surface-1 p-6">
        <div className="w-full max-w-sm text-center">
          <h1 className="text-2xl font-semibold text-text-primary">Eszközkivitel</h1>
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

  // ── 2. képernyő: kivitel / visszahozatal ──────────────────────────────────
  return (
    <main className="min-h-screen bg-surface-1 pb-24">
      <div className="mx-auto w-full max-w-3xl p-4 md:p-8">
        <header className="mb-5">
          <p className="text-[12.5px] uppercase tracking-wide text-text-muted">Eszközkivitel</p>
          <h1 className="text-xl font-semibold text-text-primary">
            {adat.projekt_nev ?? "Forgatás"}
            {adat.teszt && <span className="ml-2 rounded-full bg-surface-3 px-2 py-0.5 text-[12px] text-text-warning">TESZT</span>}
          </h1>
          <p className="mt-1 text-[13px] text-text-secondary">
            Forgatás: {datum(adat.forgatas_datuma)}
            {adat.forgatas_vege && adat.forgatas_vege !== adat.forgatas_datuma ? ` – ${datum(adat.forgatas_vege)}` : ""}
            {adat.ervenyes_eddig && ` · A kód eddig él: ${datum(adat.ervenyes_eddig)}`}
          </p>
        </header>

        {/* Mód-váltó: két nagy gomb. */}
        <div className="mb-5 grid grid-cols-2 gap-2">
          {(
            [
              ["kivitel", "Kivitel", "Mit viszel ki a forgatásra?"],
              ["vissza", "Visszahozatal", "Mit hoztál vissza?"],
            ] as const
          ).map(([kulcs, cim, leiras]) => (
            <button
              key={kulcs}
              type="button"
              onClick={() => {
                setMod(kulcs);
                setKereses("");
              }}
              className={`rounded-[var(--radius-lg)] border p-3 text-left ${
                mod === kulcs ? "border-text-accent bg-surface-2" : "border-border bg-surface-2/50 opacity-70"
              }`}
            >
              <span className="block text-[15px] font-semibold text-text-primary">{cim}</span>
              <span className="block text-[12px] text-text-muted">{leiras}</span>
            </button>
          ))}
        </div>

        {/* SÚGÓ - csak a kivitelnél: a forgatásra kiírt technika. */}
        {mod === "kivitel" && adat.ajanlott.length > 0 && (
          <section className="mb-5 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-3">
            <p className="mb-2 text-[13px] font-medium text-text-primary">Erre a forgatásra ez lett kiírva</p>
            <p className="mb-2 text-[12px] text-text-muted">
              Csak segítség - koppints arra, amit tényleg viszel, és mást is hozzáadhatsz lent a keresővel.
            </p>
            <div className="flex flex-wrap gap-2">
              {adat.ajanlott.map((a) => {
                const megvan = (tetelTerkep.get(a.id)?.kivitt_db ?? 0) > 0;
                const c = selectColor(a.kategoria?.trim() || a.nev);
                return (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => void ment(a.id, "kivitt_db", megvan ? 0 : a.db)}
                    className={`rounded-full px-3 py-1.5 text-[13.5px] ${megvan ? "ring-2 ring-text-accent" : ""}`}
                    style={{ background: c.bg, color: c.text }}
                  >
                    {megvan ? "✓ " : "+ "}
                    {a.nev}
                    {a.db > 1 ? ` (${a.db} db)` : ""}
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {/* KERESŐ - kategóriánként csoportosított, nagy találat-gombok. */}
        <section className="mb-5">
          <input
            value={kereses}
            onChange={(e) => setKereses(e.target.value)}
            placeholder={mod === "kivitel" ? "Keress eszközt, amit kiviszel…" : "Keress eszközt, amit visszahoztál…"}
            aria-label="Eszköz keresése"
            className="w-full rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-3 text-[16px] text-text-primary focus:outline-none"
          />
          {kereses.trim().length >= 2 && (
            <div className="mt-2 space-y-3 rounded-[var(--radius-lg)] border border-border bg-surface-2 p-3">
              {talalatok.length === 0 && <p className="text-[13px] text-text-muted">Nincs ilyen eszköz.</p>}
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
                        const darab = (tetelTerkep.get(e.id)?.[aktualisMezo] ?? 0) as number;
                        return (
                          <button
                            key={e.id}
                            type="button"
                            onClick={() => void ment(e.id, aktualisMezo, darab + 1)}
                            className="flex items-center justify-between rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5 text-left text-[14px] text-text-primary hover:border-text-accent/50"
                          >
                            <span className="truncate">{e.nev}</span>
                            <span className="ml-2 shrink-0 text-[13px] text-text-muted">
                              {darab > 0 ? `${darab} db ✓` : "+"}
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
        </section>

        {/* A SAJÁT LISTÁM - amit ebben a módban már beírtam. */}
        <section>
          <p className="mb-2 text-[13px] font-medium text-text-primary">
            {mod === "kivitel" ? "Amit kiviszek" : "Amit visszahoztam"}
            {listam.length > 0 && <span className="ml-1 text-text-muted">({listam.length} tétel)</span>}
          </p>
          {listam.length === 0 ? (
            <p className="rounded-[var(--radius-lg)] border border-dashed border-border p-4 text-[13px] text-text-muted">
              {mod === "kivitel"
                ? "Még nincs beírva semmi - válassz a kiírt technikából, vagy keress rá fent."
                : "Még nincs beírva semmi - keress rá fent arra, amit visszahoztál."}
            </p>
          ) : (
            <div className="space-y-1.5">
              {listam.map((t) => {
                const darab = t[aktualisMezo];
                const c = selectColor(t.kategoria?.trim() || t.nev);
                return (
                  <div
                    key={t.id}
                    className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-border bg-surface-2 px-3 py-2.5"
                  >
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: c.text }} />
                    <span className="min-w-0 flex-1 truncate text-[14.5px] text-text-primary">{t.nev}</span>
                    <div className="flex shrink-0 items-center gap-2">
                      <button
                        type="button"
                        aria-label="Kevesebb"
                        onClick={() => void ment(t.id, aktualisMezo, darab - 1)}
                        className="h-9 w-9 rounded-full border border-border text-[18px] text-text-secondary hover:bg-surface-3"
                      >
                        −
                      </button>
                      <span className="w-10 text-center text-[15px] font-semibold tabular-nums text-text-primary">
                        {darab}
                      </span>
                      <button
                        type="button"
                        aria-label="Több"
                        onClick={() => void ment(t.id, aktualisMezo, darab + 1)}
                        className="h-9 w-9 rounded-full border border-border text-[18px] text-text-secondary hover:bg-surface-3"
                      >
                        +
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        <footer className="mt-8 text-center text-[12px] text-text-muted">
          Minden beírás azonnal mentődik. Kilépéshez egyszerűen zárd be az oldalt.
        </footer>
      </div>
    </main>
  );
}
