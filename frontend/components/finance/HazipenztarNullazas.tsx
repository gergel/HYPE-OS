"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { HazipenztarNullazasElonezet } from "@/lib/api";
import { authFetch } from "@/lib/authFetch";
import { formatHuf } from "@/lib/penz";

const VEGPONT = "/api/v1/finance/hazipenztar/nullazas";

/** A HÁZIPÉNZTÁR NULLÁZÁSA (a felhasználó kérése): minden készpénzes tétel -
 * KP forgalom sor, készpénzes kiadás, készpénzes bevétel - törlése, hogy a
 * pénztár nulláról induljon (lásd backend services/hazipenztar_nullazas.py).
 *
 * Három lépés, hogy egy véletlen kattintás ne vigyen el semmit:
 *   1. előnézet - mennyi tétel és összeg törlődne;
 *   2. MENTÉS letöltése (JSON) - ebből bármelyik tétel visszaállítható;
 *   3. a megerősítő szó beírása, és csak utána a végrehajtás. */
export function HazipenztarNullazas() {
  const router = useRouter();
  const [elonezet, setElonezet] = useState<HazipenztarNullazasElonezet | null>(null);
  const [mentve, setMentve] = useState(false);
  const [szo, setSzo] = useState("");
  const [fut, setFut] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);
  const [kesz, setKesz] = useState<string | null>(null);

  async function nyit() {
    setHiba(null);
    setKesz(null);
    setFut(true);
    try {
      const res = await authFetch(VEGPONT);
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        setHiba(d?.detail ?? `Az előnézet nem tölthető be: HTTP ${res.status}`);
        return;
      }
      setElonezet(await res.json());
      setMentve(false);
      setSzo("");
    } finally {
      setFut(false);
    }
  }

  function letolt(adat: unknown, nev: string) {
    const blob = new Blob([JSON.stringify(adat, null, 1)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = nev;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function mentes() {
    setFut(true);
    setHiba(null);
    try {
      const res = await authFetch(`${VEGPONT}/mentes`);
      if (!res.ok) {
        setHiba(`A mentés nem készült el: HTTP ${res.status}`);
        return;
      }
      letolt(await res.json(), `hazipenztar-mentes-${new Date().toISOString().slice(0, 10)}.json`);
      setMentve(true);
    } finally {
      setFut(false);
    }
  }

  async function vegrehajt() {
    if (!elonezet) return;
    setFut(true);
    setHiba(null);
    try {
      const res = await authFetch(VEGPONT, { method: "POST", body: JSON.stringify({ megerosites: szo }) });
      const d = await res.json().catch(() => null);
      if (!res.ok) {
        setHiba(d?.detail ?? `A nullázás nem sikerült: HTTP ${res.status}`);
        return;
      }
      setKesz(
        `Kész: ${d.kp_forgalom_db} átvezetés/KP sor, ${d.kiadas_db} kiadás és ${d.bevetel_db} bevétel törölve.` +
          (d.mentes_kulcs ? ` A mentés a tárhelyen is megvan (${d.mentes_kulcs}).` : ""),
      );
      setElonezet(null);
      router.refresh();
    } finally {
      setFut(false);
    }
  }

  const gomb =
    "rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50";

  return (
    <div>
      {!elonezet && (
        <button type="button" onClick={nyit} disabled={fut} className={gomb}>
          {fut ? "Betöltés…" : "Házipénztár nullázása…"}
        </button>
      )}
      {elonezet && (
        <div className="space-y-3 rounded-[var(--radius)] border border-border-strong bg-bg-warning p-4">
          <p className="text-[13px] font-medium text-text-primary">Ez MINDEN készpénzes tételt töröl:</p>
          <ul className="space-y-1 text-[13px] text-text-secondary">
            <li>
              {elonezet.kp_forgalom_db} KP forgalom / átvezetés sor ({formatHuf(elonezet.kp_forgalom_osszeg)})
            </li>
            <li>
              {elonezet.kiadas_db} készpénzes kiadás a Kiadások közül ({formatHuf(elonezet.kiadas_osszeg)})
            </li>
            <li>
              {elonezet.bevetel_db} készpénzes bevétel a Bevételek közül ({formatHuf(elonezet.bevetel_osszeg)})
            </li>
          </ul>
          <p className="text-[12.5px] text-text-muted">
            Utána a Házipénztár üres, és nulláról vezethető fel újra. {elonezet.kifizetes_visszaallitas_db} megrendelői
            számla „Kifizetve” jelölése visszaáll (a projektkód újra kintlévőség lesz, amíg a készpénzes kifizetést újra
            rögzítitek), a készpénzes kiadást létrehozó TIG-ek újra „nincs kifizetve” állapotba kerülnek. A feltöltött
            számlafájlok a tárhelyen maradnak.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={mentes} disabled={fut} className={gomb}>
              {mentve ? "Mentés letöltve ✓" : "1. Mentés letöltése (JSON)"}
            </button>
            <input
              value={szo}
              onChange={(e) => setSzo(e.target.value)}
              placeholder={`2. Írd be: ${elonezet.megerosites}`}
              disabled={!mentve || fut}
              className="rounded-[var(--radius)] border border-border bg-surface-1 px-2 py-1.5 text-[13px] text-text-primary disabled:opacity-50"
            />
            <button
              type="button"
              onClick={vegrehajt}
              disabled={!mentve || fut || szo.trim() !== elonezet.megerosites}
              className="rounded-[var(--radius)] border border-border-strong bg-surface-1 px-3 py-1.5 text-[13px] font-medium text-text-danger hover:bg-surface-3 disabled:opacity-40"
            >
              {fut ? "Fut…" : "3. Nullázás"}
            </button>
            <button type="button" onClick={() => setElonezet(null)} disabled={fut} className={gomb}>
              Mégse
            </button>
          </div>
        </div>
      )}
      {kesz && <p className="mt-2 text-[12.5px] text-text-teal">{kesz}</p>}
      {hiba && <p className="mt-2 text-[12.5px] text-text-danger">{hiba}</p>}
    </div>
  );
}
