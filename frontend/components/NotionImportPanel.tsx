"use client";

import { useEffect, useRef, useState } from "react";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";

type ImportStatus = {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  /** Mely adatbázisokat futtatja/futtatta az utolsó indítás. */
  kivalasztott: string[];
  log: string[];
};

/** Egy választható Notion-adatbázis (lásd backend notion_import/katalogus.py).
 * A lista a backendről jön, hogy egy új importer magától megjelenjen itt. */
type ImporterInfo = {
  nev: string;
  cimke: string;
  kor: number;
  forrasok: string[];
  leiras: string;
  fuggosegek: string[];
};

const POLL_MS = 2000;

const KOR_CIMKE: Record<number, string> = {
  1: "1. kör – törzsadatok",
  2: "2. kör – projektek és pénzügy",
  3: "3. kör – papírok és maradék",
};

/** A Notion import elindítása/követése a böngészőből, `railway ssh` nélkül -
 * lásd backend/app/api/routes/admin_import.py: a háttérben futó import a
 * Railway-en éppen futó backend service saját processzében fut, ezért egy
 * bezárt böngészőlap/megszakadt kapcsolat nem szakítja félbe (csak egy
 * redeploy/újraindítás tenné). Admin-only - a backend 403-at ad nem-adminnak,
 * ezért ez a komponens csak akkor jelenik meg, ha a bejelentkezett
 * felhasználó admin (lásd Beállítások oldal).
 *
 * Kiválasztható, MIT importáljunk: egyetlen adatbázist, néhányat, vagy az
 * egészet. Ez azért kell, mert a teljes import a Notion rate-limitje miatt
 * akár órákig tart - ha csak egy tábla adata változott, felesleges mindent
 * újrafuttatni. */
export function NotionImportPanel() {
  const confirm = useConfirm();
  const [status, setStatus] = useState<ImportStatus | null>(null);
  const [importerek, setImporterek] = useState<ImporterInfo[]>([]);
  const [kivalasztott, setKivalasztott] = useState<Set<string>>(new Set());
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function fetchStatus() {
    const res = await authFetch("/api/v1/admin/notion-import/status");
    if (!res.ok) return;
    const body: ImportStatus = await res.json();
    setStatus(body);
    if (!body.running && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  useEffect(() => {
    fetchStatus();
    authFetch("/api/v1/admin/notion-import/importerek")
      .then((res) => (res.ok ? res.json() : []))
      .then((lista: ImporterInfo[]) => {
        setImporterek(lista);
        // Alapból minden ki van pipálva: a leggyakoribb eset a teljes import,
        // és így egy kattintással indítható marad.
        setKivalasztott(new Set(lista.map((i) => i.nev)));
      });
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (status?.running && !pollRef.current) {
      pollRef.current = setInterval(fetchStatus, POLL_MS);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status?.running]);

  function billen(nev: string) {
    setKivalasztott((elozo) => {
      const uj = new Set(elozo);
      if (uj.has(nev)) uj.delete(nev);
      else uj.add(nev);
      return uj;
    });
  }

  const mind = importerek.length > 0 && kivalasztott.size === importerek.length;
  const nevSzerint = new Map(importerek.map((i) => [i.nev, i]));
  // Csak figyelmeztetés: ha a hiányzó függőség egy korábbi importból már
  // megvan, a részleges futtatás helyes (lásd backend katalogus.py).
  const hianyzoFuggosegek = importerek
    .filter((i) => kivalasztott.has(i.nev))
    .flatMap((i) => i.fuggosegek.filter((f) => !kivalasztott.has(f)))
    .filter((f, idx, arr) => arr.indexOf(f) === idx)
    .map((f) => nevSzerint.get(f)?.cimke ?? f);

  async function start() {
    if (kivalasztott.size === 0) {
      setStartError("Válaszd ki, mely adatbázisokat importáljuk.");
      return;
    }
    const mit = mind
      ? "a TELJES Notion importot (minden adatbázis)"
      : `${kivalasztott.size} kiválasztott adatbázist`;
    if (
      !(await confirm(
        `Elindítod ${mit}? A Notion API rate limitje miatt ez sokáig tarthat – a teljes import akár órákig.`,
      ))
    ) {
      return;
    }
    setStarting(true);
    setStartError(null);
    try {
      const res = await authFetch("/api/v1/admin/notion-import", {
        method: "POST",
        // Teljes importnál üresen küldjük: a backend így a "mindent" ágon fut.
        body: JSON.stringify({ importerek: mind ? null : [...kivalasztott] }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setStartError(detail?.detail ?? `HTTP ${res.status}`);
        return;
      }
      await fetchStatus();
    } catch (err) {
      setStartError(`Hálózati hiba: ${err}`);
    } finally {
      setStarting(false);
    }
  }

  const korok = [...new Set(importerek.map((i) => i.kor))].sort((a, b) => a - b);
  const fut = !!status?.running;

  return (
    <div>
      <p className="mb-3 text-[12px] text-text-muted">
        Válaszd ki, mit hozzon át a Notionból – egyetlen adatbázist, néhányat, vagy az egészet. A körök egymásra
        épülnek, ezért a kiválasztott elemek mindig ebben a sorrendben futnak. Az import a Notionba FELTÖLTÖTT fájlokat
        (szerződések, TIG-ek, számlák) is áthozza, és a saját tárhelyünkre (R2) menti – a Notion linkjei ugyanis egy óra
        után lejárnak. A külső hivatkozások (pl. Google Docs) érintetlenül maradnak.
      </p>
      <p className="mb-3 text-[12px] text-text-muted">
        Az import <strong className="text-text-secondary">csak az újakat és a változásokat</strong> hozza át: amit itt,
        a HYPE OS-ben módosítottál az előző import óta, azt nem írja felül. Ha tehát egy TIG-et vagy egy utókövetést itt
        fejeztél be, a Notion (elavult vagy hiányzó) adata nem írja vissza. A napló mezőnként megmutatja, mit hagyott
        érintetlenül.
      </p>

      {importerek.length > 0 && (
        <div className="mb-4 rounded-[var(--radius)] border border-border p-3">
          <div className="mb-2 flex flex-wrap items-center gap-3">
            <span className="text-[12.5px] text-text-primary">
              {mind ? "Minden adatbázis kiválasztva" : `${kivalasztott.size} / ${importerek.length} kiválasztva`}
            </span>
            <button
              type="button"
              disabled={fut}
              onClick={() => setKivalasztott(new Set(importerek.map((i) => i.nev)))}
              className="text-[12px] text-text-accent hover:underline disabled:opacity-50"
            >
              Mindet
            </button>
            <button
              type="button"
              disabled={fut}
              onClick={() => setKivalasztott(new Set())}
              className="text-[12px] text-text-accent hover:underline disabled:opacity-50"
            >
              Egyiket se
            </button>
          </div>

          {korok.map((kor) => {
            const koreiek = importerek.filter((i) => i.kor === kor);
            const mindKor = koreiek.every((i) => kivalasztott.has(i.nev));
            return (
              <div key={kor} className="mt-3 first:mt-0">
                <div className="mb-1 flex items-center gap-2">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-text-muted">
                    {KOR_CIMKE[kor] ?? `${kor}. kör`}
                  </span>
                  <button
                    type="button"
                    disabled={fut}
                    onClick={() =>
                      setKivalasztott((elozo) => {
                        const uj = new Set(elozo);
                        for (const i of koreiek) {
                          if (mindKor) uj.delete(i.nev);
                          else uj.add(i.nev);
                        }
                        return uj;
                      })
                    }
                    className="text-[11px] text-text-accent hover:underline disabled:opacity-50"
                  >
                    {mindKor ? "kikapcsol" : "mind"}
                  </button>
                </div>
                <div className="grid grid-cols-1 gap-1 md:grid-cols-2">
                  {koreiek.map((i) => (
                    <label
                      key={i.nev}
                      className="flex cursor-pointer items-start gap-2 rounded-[var(--radius)] px-1.5 py-1 text-[12.5px] hover:bg-surface-3"
                      title={i.leiras}
                    >
                      <input
                        type="checkbox"
                        className="mt-0.5"
                        checked={kivalasztott.has(i.nev)}
                        disabled={fut}
                        onChange={() => billen(i.nev)}
                      />
                      <span>
                        <span className="text-text-primary">{i.cimke}</span>
                        <span className="block text-[11px] text-text-muted">{i.forrasok.join(", ")}</span>
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            );
          })}

          {hianyzoFuggosegek.length > 0 && (
            <p className="mt-3 border-t border-border pt-2 text-[11.5px] text-text-secondary">
              Megjegyzés: a kiválasztottak általában ezek után futnak: {hianyzoFuggosegek.join(", ")}. Ha azok korábban
              már lefutottak, ez rendben van – ez csak az első, üres adatbázison induló importnál számít.
            </p>
          )}
        </div>
      )}

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={start}
          disabled={starting || fut || kivalasztott.size === 0}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          {fut ? "Fut…" : mind ? "Teljes import indítása" : `Import indítása (${kivalasztott.size})`}
        </button>
        {fut && <span className="text-[12px] text-text-muted">Elindítva: {status?.started_at}</span>}
      </div>

      {startError && <p className="mb-3 text-[12px] text-text-danger">{startError}</p>}
      {status && !status.running && status.finished_at && (
        <p className="mb-2 text-[12px] text-text-muted">
          Utolsó futás vége: {status.finished_at}
          {status.kivalasztott?.length > 0 && status.kivalasztott.length < importerek.length && (
            <span> · {status.kivalasztott.length} adatbázis</span>
          )}
          {status.error && <span className="text-text-danger"> - hiba: {status.error}</span>}
        </p>
      )}
      {status && status.log.length > 0 && (
        <pre className="max-h-72 overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-1 p-3 text-[11px] leading-relaxed whitespace-pre-wrap text-text-secondary">
          {status.log.join("\n")}
        </pre>
      )}
    </div>
  );
}
