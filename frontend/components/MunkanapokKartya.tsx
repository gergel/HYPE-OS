"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/authFetch";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { HONAP_NEVEK } from "@/lib/diszpoSzin";
// A formatHuf a KLIENS-BIZTOS lib/penz-ből jön, nem a lib/api-ból - az utóbbi
// a `next/headers`-t is behúzza (szerver-oldali cookie-olvasáshoz), ami
// klienskomponensben build-hibát okozna. Ugyanaz a minta, mint a
// lib/diszpoSzin.ts-nél.
import { formatHuf } from "@/lib/penz";
import type { DiszpoHaviAllas } from "@/lib/api";

/** A "Munkanapok" összesítő - KÜLÖN kliens-komponensben, mert a hónapváltás
 * korábban a teljes oldalt (Link-navigációval) rendereltette újra, és ezzel
 * elveszett a fölötte lévő rács görgetési pozíciója. Ez a kártya saját
 * hónap-állapotot tart és a saját adatát maga kéri le - a tábla fölötte
 * tehát valóban külön listaként viselkedik, nem érinti a rácsot. */
export function MunkanapokKartya({ kezdoEv, kezdoHonap }: { kezdoEv: number; kezdoHonap: number }) {
  const [ev, setEv] = useState(kezdoEv);
  const [honap, setHonap] = useState(kezdoHonap);
  const [haviAllas, setHaviAllas] = useState<DiszpoHaviAllas[] | null>(null);

  useEffect(() => {
    let elve = false;
    authFetch(`/api/v1/diszpo-tabla/munkanapok/${ev}/${honap}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((adat: DiszpoHaviAllas[]) => {
        if (!elve) setHaviAllas(adat);
      })
      .catch(() => {
        if (!elve) setHaviAllas([]);
      });
    return () => {
      elve = true;
    };
  }, [ev, honap]);

  function lepj(irany: number) {
    const d = new Date(ev, honap - 1 + irany, 1);
    setEv(d.getFullYear());
    setHonap(d.getMonth() + 1);
  }

  const adat = haviAllas ?? [];
  const latszikPenz = adat.some((a) => a.penzugyi_adat);
  const elfogyott = adat.filter((a) => a.plusz_napok.length > 0);

  return (
    <Card title={`Munkanapok – ${ev}. ${HONAP_NEVEK[honap - 1]}`}>
      {/* HÓNAPLÉPTETŐ: kliens-oldali állapot, nem URL/Link - a fölötte lévő
          rács görgetése ettől nem áll vissza. */}
      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={() => lepj(-1)}
          className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3"
        >
          ← Előző
        </button>
        <button
          type="button"
          onClick={() => lepj(1)}
          className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3"
        >
          Következő →
        </button>
        <span className="ml-2 flex flex-wrap gap-1">
          {HONAP_NEVEK.map((nev, i) => (
            <button
              key={nev}
              type="button"
              onClick={() => setHonap(i + 1)}
              className={`rounded-[var(--radius)] px-2 py-1 text-[12px] ${
                i + 1 === honap ? "bg-bg-accent text-text-accent" : "text-text-muted hover:bg-surface-3"
              }`}
            >
              {nev.slice(0, 3)}.
            </button>
          ))}
        </span>
      </div>

      {haviAllas === null ? (
        <p className="text-[13px] text-text-secondary">Betöltés…</p>
      ) : adat.length === 0 ? (
        <p className="text-[13px] text-text-secondary">
          Ebben a hónapban még nincs kiszínezett munkanap – vagy az oszlopok nincsenek munkatárshoz kötve. A
          kötés a táblázatban, az oszlop egy cellájára kattintva adható meg.
        </p>
      ) : (
        <>
          <p className="mb-3 text-[12.5px] text-text-secondary">
            Munkanapnak számít a <b>zöld</b>, a <b>kék</b> és az <b>üresen hagyott</b> nap is – az utóbbi azért,
            mert a napja le volt kötve, csak nem tudtunk rá munkát adni.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Munkatárs</th>
                  <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Munkanap</th>
                  {latszikPenz && (
                    <>
                      <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Szerződve</th>
                      <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Mikor fogy el</th>
                      <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Napidíj</th>
                      <th className="py-1.5 text-right font-medium text-text-secondary">Plusz nap díja</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {adat.map((a) => (
                  <tr key={a.employee_id} className="border-b border-border last:border-0">
                    <td className="py-2 pr-6 text-text-primary">{a.employee_nev ?? `#${a.employee_id}`}</td>
                    <td className="py-2 pr-6 text-right tabular-nums text-text-primary">{a.munkanapok}</td>
                    {latszikPenz && (
                      <>
                        <td className="py-2 pr-6 text-right tabular-nums text-text-secondary">
                          {a.szerzodott_napok ?? "–"}
                        </td>
                        <td className="py-2 pr-6">
                          {a.plusz_napok.length > 0 ? (
                            <span className="flex flex-wrap items-center gap-2">
                              <StatusBadge label={`${a.plusz_napok.length} plusz nap`} tone="warning" />
                              <span className="text-[12px] text-text-muted">
                                {a.hatarnap} után: {a.plusz_napok.join(", ")}
                              </span>
                            </span>
                          ) : a.szerzodott_napok ? (
                            <span className="text-text-muted">a kereten belül</span>
                          ) : (
                            <span className="text-text-muted">nincs megadva napszám</span>
                          )}
                        </td>
                        <td className="py-2 pr-6 text-right tabular-nums text-text-secondary">
                          {a.napi_dij != null ? formatHuf(a.napi_dij) : "–"}
                        </td>
                        <td className="py-2 text-right tabular-nums text-text-secondary">
                          {a.plusz_nap_napi_dij != null ? (
                            formatHuf(a.plusz_nap_napi_dij)
                          ) : (
                            <span className="text-text-muted" title="Enélkül a plusz nap is a rendes napidíjon számol">
                              nincs megadva
                            </span>
                          )}
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {latszikPenz && elfogyott.length > 0 && (
            <p className="mt-3 text-[12.5px] text-text-secondary">
              {elfogyott.length} munkatársnál elfogyott a havi szerződött napszám. A határnap utáni forgatásaikon
              a <b>plusz nap napidíját</b> számoljuk a projekt önköltségébe – akinél az nincs megadva, ott marad a
              rendes napidíj (a hiányzó adat nem árazhat át semmit csendben).
            </p>
          )}
        </>
      )}
    </Card>
  );
}
