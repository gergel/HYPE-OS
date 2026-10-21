"use client";

import { useState } from "react";
import { ChevronDown, Trophy } from "lucide-react";
import { HONAP_NEVEK } from "@/lib/ido";
import type { VagoHonap } from "@/lib/api";

function honapCimke(ev: number, honap: number): string {
  return `${ev}. ${HONAP_NEVEK[honap - 1]}`;
}

/** A korábbi hónapok dicsőségtáblája: ki nyert, ki hányadik lett - és
 * adminként LENYITHATÓ a teljes pont-bontás is (a felhasználó kérése):
 * ki mivel (ellenőrzésbe tett anyag, vágott órák, elsőre jó / javítás)
 * és mennyi pontot szerzett abban a hónapban.
 *
 * A bontás adata ugyanabból a lekérésből jön, mint a lista (a /korabbi
 * végpont a teljes állást adja) - a lenyitás nem indít új kérést. */
export function KorabbiHonapok({
  honapok,
  reszletezheto,
}: {
  honapok: VagoHonap[];
  /** Szerkesztési (admin) joggal nyitható le a részletes bontás. */
  reszletezheto: boolean;
}) {
  const [nyitva, setNyitva] = useState<string | null>(null);

  if (honapok.length === 0) return null;
  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6">
      <h2 className="t-section mb-4">Korábbi hónapok</h2>
      <div className="space-y-5">
        {honapok.map((h) => {
          const kulcs = `${h.ev}-${h.honap}`;
          const lenyitva = nyitva === kulcs;
          return (
            <div key={kulcs} className="border-b border-border pb-5 last:border-0 last:pb-0">
              <div className="mb-2 flex flex-wrap items-baseline justify-between gap-3">
                <span className="flex items-center gap-2">
                  {/* A kupa a győztes mellett - a dicsőségtáblán ez az egyetlen
                      dolog, amit messziről is látni kell. */}
                  <Trophy size={15} className="text-text-warning" aria-hidden />
                  <span className="text-[14px] font-medium text-text-primary">{honapCimke(h.ev, h.honap)}</span>
                  {h.gyoztes_nev && (
                    <span className="text-[13px] text-text-secondary">
                      – {h.gyoztes_nev} ({h.gyoztes_pont} pont)
                    </span>
                  )}
                </span>
                <span className="flex items-center gap-3">
                  {h.nyeremeny && (
                    <span className="flex items-center gap-2 text-[12.5px] text-text-muted">
                      {/* Bélyegkép: a régi hónapoknál a kép emlékeztet rá, mi volt
                          a tét - egy név önmagában pár hónap múlva nem mond semmit. */}
                      {h.kep_url && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={h.kep_url}
                          alt=""
                          className="h-7 w-10 rounded-[var(--radius)] border border-border object-cover"
                        />
                      )}
                      Nyeremény: {h.nyeremeny}
                    </span>
                  )}
                  {reszletezheto && (
                    <button
                      type="button"
                      onClick={() => setNyitva(lenyitva ? null : kulcs)}
                      className="flex items-center gap-1 text-[12.5px] text-text-secondary hover:text-text-primary"
                    >
                      Részletek
                      <ChevronDown
                        size={14}
                        className={`transition-transform ${lenyitva ? "rotate-180" : ""}`}
                      />
                    </button>
                  )}
                </span>
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-1">
                {h.allas
                  .filter((a) => a.helyezes > 0)
                  .map((a) => (
                    <span key={a.employee_id} className="text-[12.5px] text-text-secondary">
                      <span
                        className={`mr-1 tabular-nums ${a.helyezes === 1 ? "text-text-warning" : "text-text-muted"}`}
                      >
                        {a.helyezes}.
                      </span>
                      {a.nev}
                      <span className="ml-1 tabular-nums text-text-muted">{a.pont}</span>
                    </span>
                  ))}
              </div>
              {lenyitva && <PontBontas honap={h} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Egy lezárt hónap teljes pont-bontása - ugyanazok az oszlopok, mint a folyó
 * hónap "Pontok bontása" tábláján, csak OLVASÁSRA: a munkanap itt már nem
 * szerkeszthető, mert a kihirdetett eredményen úgysem változtatna (a győztes
 * hónapzáráskor kőbe vésődik, lásd backend services/vagoi_jatek.havi_zaras). */
function PontBontas({ honap }: { honap: VagoHonap }) {
  return (
    <div className="mt-3 overflow-x-auto rounded-[var(--radius)] border border-border bg-surface-1 p-4">
      <table className="os-table min-w-full border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-border">
            <th className="py-2 pr-4 text-left font-medium text-text-muted">Név</th>
            <th className="py-2 pr-4 text-right font-medium text-text-muted">Ellenőrzésbe tett</th>
            <th className="py-2 pr-4 text-right font-medium text-text-muted">Vágás</th>
            <th className="py-2 pr-4 text-right font-medium text-text-muted">Elsőre jó / javítás</th>
            <th className="py-2 pr-4 text-right font-medium text-text-muted">Nyers pont</th>
            <th className="py-2 pr-4 text-right font-medium text-text-muted">Munkanap</th>
            <th className="py-2 text-right font-medium text-text-muted">Pont</th>
          </tr>
        </thead>
        <tbody>
          {honap.allas.map((a) => (
            <tr key={a.employee_id} className="border-b border-border last:border-0">
              <td className="py-2.5 pr-4 text-text-primary">{a.nev}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">
                {a.ellenorzes_db} db
                <span className="ml-1.5 text-[11px] text-text-muted">{a.ellenorzes_pont} p</span>
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">
                {Math.round(a.vagas_perc / 60)} óra
                <span className="ml-1.5 text-[11px] text-text-muted">{a.vagas_pont} p</span>
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">
                {a.jovahagyas_db > 0 && <span className="text-text-success">{a.jovahagyas_db} jó</span>}
                {a.jovahagyas_db > 0 && a.javitas_db > 0 && " · "}
                {a.javitas_db > 0 && <span className="text-text-danger">{a.javitas_db} javítás</span>}
                {a.jovahagyas_db === 0 && a.javitas_db === 0 && "–"}
                {(a.jovahagyas_db > 0 || a.javitas_db > 0) && (
                  <span className="ml-1.5 text-[11px] text-text-muted">
                    {a.kimenet_pont > 0 ? "+" : ""}
                    {a.kimenet_pont} p
                  </span>
                )}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">{a.nyers_pont}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums text-text-secondary">{a.munkanap}</td>
              <td className="py-2.5 text-right font-semibold tabular-nums text-text-primary">{a.pont}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
