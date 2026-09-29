"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { UjAjanlatModal } from "./UjAjanlatModal";
import {
  MARKAK,
  STATUSZOK,
  type AjanlatListaElem,
  type Sablon,
  ajanlatSzam,
  datumSzoveg,
  ft,
  hivas,
  kuld,
  statusz,
} from "./quote";

/** Árajánlatok listája: szám, ügyfél, projekt, dátum, végösszeg, státusz,
 * márka - szűrőkkel és az „Új árajánlat” gombbal. */
export function AjanlatLista({ canCreate, canEdit }: { canCreate: boolean; canEdit: boolean }) {
  const [sorok, setSorok] = useState<AjanlatListaElem[] | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);
  const [szoveg, setSzoveg] = useState("");
  const [allapot, setAllapot] = useState("");
  const [marka, setMarka] = useState("");
  const [tol, setTol] = useState("");
  const [ig, setIg] = useState("");
  const [uj, setUj] = useState(false);
  const [uresAlap, setUresAlap] = useState(false);
  const [seedBusy, setSeedBusy] = useState(false);
  const idozito = useRef<ReturnType<typeof setTimeout> | null>(null);

  const betolt = useCallback(async () => {
    const p = new URLSearchParams();
    if (szoveg.trim()) p.set("q", szoveg.trim());
    if (allapot) p.set("status", allapot);
    if (marka) p.set("brand", marka);
    if (tol) p.set("date_from", tol);
    if (ig) p.set("date_to", ig);
    try {
      setSorok(await hivas<AjanlatListaElem[]>(`?${p.toString()}`));
      setHiba(null);
    } catch (e) {
      setHiba((e as Error).message);
    }
  }, [szoveg, allapot, marka, tol, ig]);

  useEffect(() => {
    if (idozito.current) clearTimeout(idozito.current);
    idozito.current = setTimeout(betolt, 250);
  }, [betolt]);

  useEffect(() => {
    hivas<Sablon[]>("/templates")
      .then((t) => setUresAlap(t.length === 0))
      .catch(() => undefined);
  }, []);

  async function alapadatok() {
    setSeedBusy(true);
    try {
      await kuld("/seed", "POST");
      setUresAlap(false);
    } catch (e) {
      setHiba((e as Error).message);
    } finally {
      setSeedBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {uresAlap && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] border border-border bg-bg-warning px-4 py-3 text-[13px] text-text-warning">
          <span>
            Az alap tétel-katalógus (98 tétel) és a 10 sablon még nincs betöltve. Betöltés után minden szerkeszthető.
          </span>
          {canEdit && (
            <button type="button" disabled={seedBusy} onClick={alapadatok} className="btn btn-primary text-[13px]">
              {seedBusy ? "Betöltés…" : "Alapadatok betöltése"}
            </button>
          )}
        </div>
      )}
      <Card
        title="Árajánlatok"
        actions={
          canCreate ? (
            <button type="button" onClick={() => setUj(true)} className="btn btn-primary flex items-center gap-1.5 text-[13px]">
              <Plus size={14} /> Új árajánlat
            </button>
          ) : null
        }
      >
        <div className="mb-4 flex flex-wrap items-end gap-2">
          <input
            className="field min-w-[220px] flex-1"
            placeholder="Keresés: szám, ügyfél, projekt, helyszín…"
            value={szoveg}
            onChange={(e) => setSzoveg(e.target.value)}
          />
          <select className="field w-auto" value={allapot} onChange={(e) => setAllapot(e.target.value)} aria-label="Státusz">
            <option value="">Minden státusz</option>
            {STATUSZOK.map((s) => (
              <option key={s.ertek} value={s.ertek}>
                {s.cimke}
              </option>
            ))}
          </select>
          <select className="field w-auto" value={marka} onChange={(e) => setMarka(e.target.value)} aria-label="Márka">
            <option value="">Minden márka</option>
            {MARKAK.map((m) => (
              <option key={m.ertek} value={m.ertek}>
                {m.cimke}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-[12px] text-text-muted">
            Dátum
            <input type="date" className="field w-auto" value={tol} onChange={(e) => setTol(e.target.value)} aria-label="Dátumtól" />
            –
            <input type="date" className="field w-auto" value={ig} onChange={(e) => setIg(e.target.value)} aria-label="Dátumig" />
          </label>
        </div>
        {hiba && <p className="mb-3 rounded-[var(--radius)] bg-bg-danger px-3 py-2 text-[13px] text-text-danger">{hiba}</p>}
        {sorok === null ? (
          <p className="text-[13px] text-text-muted">Betöltés…</p>
        ) : sorok.length === 0 ? (
          <p className="text-[13px] text-text-secondary">Nincs a szűrésnek megfelelő árajánlat.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-border text-left text-text-secondary">
                  <th className="py-1.5 pr-4 font-medium">Szám</th>
                  <th className="py-1.5 pr-4 font-medium">Ügyfél</th>
                  <th className="py-1.5 pr-4 font-medium">Projekt</th>
                  <th className="py-1.5 pr-4 font-medium">Dátum</th>
                  <th className="py-1.5 pr-4 text-right font-medium">Végösszeg (nettó)</th>
                  <th className="py-1.5 pr-4 font-medium">Státusz</th>
                  <th className="py-1.5 font-medium">Márka</th>
                </tr>
              </thead>
              <tbody>
                {sorok.map((a) => {
                  const s = statusz(a.status);
                  return (
                    <tr key={a.id} className="border-b border-border last:border-0 hover:bg-surface-3/40">
                      <td className="whitespace-nowrap py-2 pr-4">
                        <Link href={`/arajanlatok/${a.id}`} className="font-mono text-[12.5px] text-text-accent hover:underline">
                          {ajanlatSzam(a)}
                        </Link>
                      </td>
                      <td className="py-2 pr-4 text-text-secondary">{a.client_name ?? "–"}</td>
                      <td className="py-2 pr-4">
                        <Link href={`/arajanlatok/${a.id}`} className="text-text-primary hover:underline">
                          {a.project_name || "(névtelen)"}
                        </Link>
                      </td>
                      <td className="whitespace-nowrap py-2 pr-4 text-text-secondary">
                        {a.event_date_from ? datumSzoveg(a.event_date_from, a.event_date_to) : (a.created_at ?? "").slice(0, 10)}
                      </td>
                      <td className="whitespace-nowrap py-2 pr-4 text-right font-mono text-[12.5px]">
                        {ft(a.net_total)}
                        {a.pricing_mode === "monthly" && <span className="ml-1 text-[11px] text-text-muted">(keret)</span>}
                      </td>
                      <td className="py-2 pr-4">
                        <StatusBadge label={s.cimke} tone={s.tone} />
                      </td>
                      <td className="py-2">
                        <StatusBadge label={a.brand === "CB" ? "ContentBee" : "HYPE"} tone={a.brand === "CB" ? "orange" : "neutral"} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {uj && <UjAjanlatModal onClose={() => setUj(false)} />}
    </div>
  );
}
