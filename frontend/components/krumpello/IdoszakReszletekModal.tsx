"use client";

import { useEffect, useState } from "react";
import { ModalReteg } from "@/components/ModalReteg";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { formatFt } from "@/lib/ido";
import type { KrumpelloIdoszakReszletek } from "@/lib/api";

/** Egy időszak NAPI BONTÁSA: melyik napból mennyi megy utalással, mennyi
 * készpénzben, és melyik nap mi szerint volt bejelentve.
 *
 * Ez az a nézet, amiből a kifizetés ellenőrizhető: az összesítő két száma
 * (utalás / készpénz) itt bontható vissza napokra, tehát ha valami nem stimmel,
 * látszik, melyik napon. */
export function IdoszakReszletekModal({ idoszakId, onClose }: { idoszakId: number; onClose: () => void }) {
  const [adat, setAdat] = useState<KrumpelloIdoszakReszletek | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  useEffect(() => {
    let el = true;
    authFetch(`/api/v1/krumpello/idoszakok/${idoszakId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`${res.status}`);
        return res.json();
      })
      .then((json) => el && setAdat(json))
      .catch((err) => el && setHiba(String(err)));
    return () => {
      el = false;
    };
  }, [idoszakId]);

  return (
    <ModalReteg onClose={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {hiba && <p className="p-5 text-[13px] text-text-danger">Nem sikerült betölteni: {hiba}</p>}
        {!adat && !hiba && <p className="p-5 text-[13px] text-text-muted">Betöltés…</p>}

        {adat && (
          <>
            <div className="border-b border-border px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-[15px] font-medium text-text-primary">
                  {adat.dolgozo_nev} · {adat.kezdet} – {adat.veg ?? "azóta is tart"}
                </h3>
                {adat.teljesen_kifizetve ? (
                  <StatusBadge label="Fizetve" tone="success" />
                ) : (
                  <StatusBadge label={`Még jár: ${formatFt(adat.hatralek)}`} tone="warning" />
                )}
              </div>
              <p className="mt-1 text-[12.5px] text-text-muted">
                {adat.bejelentes_cimke}
                {adat.napi_ber ? ` · bejelentett napi bér: ${formatFt(adat.napi_ber)}` : ""}
                {adat.nev ? ` · ${adat.nev}` : ""}
              </p>

              <div className="mt-3 flex flex-wrap gap-6">
                <Szam cimke="Ledolgozott óra" ertek={`${adat.ora_osszesen.toLocaleString("hu-HU")} óra`} />
                <Szam cimke="Járandóság" ertek={formatFt(adat.jarandosag)} />
                <Szam cimke="Ebből utalás" ertek={formatFt(adat.utalando)} />
                <Szam cimke="Ebből készpénz" ertek={formatFt(adat.keszpenz)} />
                <Szam cimke="Borravaló" ertek={formatFt(adat.borravalo)} />
              </div>
            </div>

            <div className="p-5">
              {adat.napok.length === 0 ? (
                <p className="text-[12.5px] text-text-muted">Ebbe az időszakba még nem esik ledolgozott nap.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse text-[13px]">
                    <thead>
                      <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-text-muted">
                        <th className="py-2 pr-3 font-medium">Nap</th>
                        <th className="py-2 pr-3 text-right font-medium">Óra</th>
                        <th className="py-2 pr-3 text-right font-medium">Órabér</th>
                        <th className="py-2 pr-3 text-right font-medium">Járandóság</th>
                        <th className="py-2 pr-3 font-medium">Bejelentés</th>
                        <th className="py-2 pr-3 text-right font-medium">Utalás</th>
                        <th className="py-2 pr-3 text-right font-medium">Készpénz</th>
                        <th className="py-2 font-medium">Állapot</th>
                      </tr>
                    </thead>
                    <tbody>
                      {adat.napok.map((n) => (
                        <tr key={n.munkaora_id} className="border-b border-border last:border-0">
                          <td className="py-2 pr-3 text-text-primary">{n.datum}</td>
                          <td className="py-2 pr-3 text-right text-text-secondary">{n.ora}</td>
                          <td className="py-2 pr-3 text-right text-text-secondary">{formatFt(n.orabar)}</td>
                          <td className="py-2 pr-3 text-right text-text-primary">{formatFt(n.jarandosag)}</td>
                          <td className="py-2 pr-3 text-text-secondary">
                            {n.bejelentes_cimke}
                            {/* Az örökölt és a kézzel felülírt érték nem
                                ugyanaz: ha valaki egy napot kivett a
                                bejelentésből, azt látni kell. */}
                            {n.bejelentes_forrasa === "nap" && (
                              <span className="ml-1 text-[11px] text-text-muted">(napra megadva)</span>
                            )}
                          </td>
                          <td className="py-2 pr-3 text-right text-text-secondary">{formatFt(n.utalando)}</td>
                          <td
                            className={`py-2 pr-3 text-right ${n.tulfizetett ? "text-text-danger" : "text-text-secondary"}`}
                            title={
                              n.tulfizetett
                                ? "A bejelentett napi bér többet fizet, mint amennyi aznap járt – az időszak végén kiegyenlítődik."
                                : undefined
                            }
                          >
                            {formatFt(n.keszpenz)}
                          </td>
                          <td className="py-2">
                            {n.kifizetve ? (
                              <span className="text-[11.5px] text-text-muted">
                                Fizetve{n.kifizetes_datuma ? ` (${n.kifizetes_datuma})` : ""}
                              </span>
                            ) : (
                              <span className="text-[11.5px] text-text-primary">Még jár</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <div className="flex justify-end border-t border-border px-5 py-3">
              <button
                type="button"
                onClick={onClose}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
              >
                Bezárás
              </button>
            </div>
          </>
        )}
      </div>
    </ModalReteg>
  );
}

function Szam({ cimke, ertek }: { cimke: string; ertek: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-text-muted">{cimke}</p>
      <p className="text-[15px] text-text-primary">{ertek}</p>
    </div>
  );
}
