"use client";

import type { TigTetel } from "@/lib/api";

/** Egy papír-tétel: kinek a munkája, melyik projekten. A szerződés-tétel és a
 * TIG-tétel alakja azonos (lásd backend models/contract.py ContractTetel,
 * models/performance_certificate.py PerformanceCertificateTetel). */
export type PapirTetel = TigTetel;

/** Egy tétel azonosítója a felületen: melyik ember melyik projekten végzett
 * munkája. */
export function tetelKulcs(t: { project_id: number; employee_id: number }): string {
  return `${t.project_id}:${t.employee_id}`;
}

/** Mit fed le ez a papír: kinek a munkáját, melyik projekten.
 *
 * Ugyanaz az ESETI SZERZŐDÉSNÉL és a TIG-nél - és jó, hogy ugyanaz: ha három
 * nap forgatásról egy TIG készül, akkor egy szerződésnek is kell tartoznia
 * hozzá, ugyanazzal a tétellistával.
 *
 * Két dolgot old meg egyszerre:
 * - a projekten belül több ember munkáját (ha valaki más nevében is számláz),
 * - és MÁS projektek munkáit (ha valaki több forgatást egy számlán küld be).
 *
 * A tételenkénti összeg szándékosan elhagyható: összevont számlánál nem mindig
 * tudható, mi mennyibe került. Ha kitöltik, a projekt-jövedelmezőség abból
 * számol; ha nem, a TIG fejösszege marad az egyetlen igazság - egyenlően
 * SOSEM osztjuk szét, mert az kitalált számokat vinne a kimutatásokba. */
export function PapirTetelValaszto({
  tetelek,
  kivalasztott,
  osszegek,
  toltodik,
  tiltva,
  onBillen,
  onOsszeg,
  fejOsszeg,
  cim,
  leiras,
}: {
  tetelek: PapirTetel[];
  kivalasztott: Set<string>;
  osszegek: Record<string, string>;
  toltodik: boolean;
  tiltva: boolean;
  onBillen: (kulcs: string) => void;
  onOsszeg: (kulcs: string, ertek: string) => void;
  fejOsszeg: string;
  cim: string;
  leiras: string;
}) {
  if (toltodik) {
    return <p className="mt-4 border-t border-border pt-4 text-[12px] text-text-muted">Tételek betöltése…</p>;
  }
  if (tetelek.length === 0) return null;

  const bontott = tetelek
    .filter((t) => kivalasztott.has(tetelKulcs(t)))
    .map((t) => Number((osszegek[tetelKulcs(t)] ?? "").trim()))
    .filter((n) => !Number.isNaN(n) && n > 0);
  const bontasOsszege = bontott.reduce((a, b) => a + b, 0);
  const fej = Number(fejOsszeg);
  const elter = bontott.length > 0 && !Number.isNaN(fej) && fej > 0 && Math.abs(bontasOsszege - fej) > 0.5;

  return (
    <div className="mt-4 border-t border-border pt-4">
      <p className="mb-1 text-[13px] font-medium text-text-primary">{cim}</p>
      <p className="mb-3 text-[12px] text-text-muted">{leiras}</p>
      <div className="flex flex-col gap-1.5">
        {tetelek.map((t) => {
          const kulcs = tetelKulcs(t);
          const be = kivalasztott.has(kulcs);
          return (
            <div key={kulcs} className="flex flex-wrap items-center gap-2 text-[13px]">
              <label className="flex min-w-[280px] flex-1 items-center gap-2 text-text-primary">
                <input type="checkbox" checked={be} onChange={() => onBillen(kulcs)} disabled={tiltva} />
                <span>
                  {t.employee_nev ?? `#${t.employee_id}`}
                  <span className="text-text-muted">
                    {" – "}
                    {t.projektkod ? `${t.projektkod} · ` : ""}
                    {t.project_nev ?? `#${t.project_id}`}
                    {t.forgatas_datuma ? ` (${t.forgatas_datuma})` : ""}
                  </span>
                </span>
              </label>
              <input
                type="number"
                value={osszegek[kulcs] ?? ""}
                onChange={(e) => onOsszeg(kulcs, e.target.value)}
                disabled={tiltva || !be}
                placeholder="ebből ennyi az övé (nem kötelező)"
                className="w-[240px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[12px] text-text-primary focus:outline-none disabled:opacity-40"
              />
            </div>
          );
        })}
      </div>
      {elter && (
        <p className="mt-2 text-[12px] text-text-secondary">
          A kitöltött tételek összege {bontasOsszege.toLocaleString("hu-HU")} Ft, a papír nettó összege{" "}
          {fej.toLocaleString("hu-HU")} Ft. Ez nem hiba – a bontás lehet részleges –, de érdemes ránézni.
        </p>
      )}
    </div>
  );
}
