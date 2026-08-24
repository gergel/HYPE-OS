"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Circle, Clock } from "lucide-react";
import { formatFt } from "@/lib/ido";
import type { BelsosTigHonap } from "@/lib/api";

/** A hónap-állapotok megjelenése. A "lezárva" azt jelenti, hogy MINDEN belsős
 * munkatárs rendben van: kiküldött TIG + feltöltött és kifizetett számla, vagy
 * kihagyva. A "tig_kesz" a köztes állapot: a TIG-ek elkészültek, csak a
 * számla/kifizetés van hátra. */
const ALLAPOTOK: Record<string, { label: string; szin: string; hatter: string; Ikon: typeof CheckCircle2 }> = {
  lezarva: { label: "Kész", szin: "text-text-success", hatter: "bg-bg-success", Ikon: CheckCircle2 },
  tig_kesz: { label: "TIG kész, számla hátravan", szin: "text-text-warning", hatter: "bg-bg-warning", Ikon: Clock },
  folyamatban: { label: "Folyamatban", szin: "text-text-warning", hatter: "bg-bg-warning", Ikon: Clock },
  nincs_elkezdve: { label: "Nincs elkezdve", szin: "text-text-muted", hatter: "bg-surface-3", Ikon: Circle },
};

function huDatum(iso: string): string {
  return iso.replaceAll("-", ". ") + ".";
}

/** Havi "mappázás" a Belsős TIG-hez: hónaponként külön dobozban látszik, melyik
 * hónap van kész, és ahol nincs, ott pontosan kinek mi hiányzik. A hónapok
 * szándékosan külön keretben vannak, hogy ne folyjanak egybe - egy hónap
 * kinyitva mutatja a saját teendőit, a "Megnyitás" pedig átvisz az adott hónap
 * teljes kezelőfelületére.
 *
 * Alapból azok a hónapok vannak nyitva, ahol már ELKEZDŐDÖTT a munka, maradt
 * teendő, és lejárt a határidő - azokkal kell foglalkozni. Egy el sem kezdett
 * régi hónapot nem nyitunk ki: ott a fejléc ("0/3 rendben · 3 hiányzik") már
 * mindent elmond, a kinyitva ismételt "Nincs elkezdve" sorok csak elfednék az
 * igazi teendőket. */
export function BelsosTigHaviAttekintes({ honapok }: { honapok: BelsosTigHonap[] }) {
  const [nyitott, setNyitott] = useState<string[]>(() =>
    honapok.filter((h) => h.keses && h.allapot !== "nincs_elkezdve").map((h) => `${h.ev}-${h.honap}`),
  );

  if (honapok.length === 0) {
    return <p className="text-[13px] text-text-muted">Még nincs egyetlen hónap sem.</p>;
  }

  function toggle(kulcs: string) {
    setNyitott((elozo) => (elozo.includes(kulcs) ? elozo.filter((k) => k !== kulcs) : [...elozo, kulcs]));
  }

  const keses = honapok.filter((h) => h.keses).length;
  const lezaratlan = honapok.filter((h) => h.allapot !== "lezarva").length;

  return (
    <div>
      <p className="mb-3 text-[13px] text-text-secondary">
        {honapok.length} hónap · {lezaratlan} még nincs lezárva
        {keses > 0 && <span className="text-text-danger"> · {keses} késésben</span>}
      </p>

      <div className="space-y-2">
        {honapok.map((h) => {
          const kulcs = `${h.ev}-${h.honap}`;
          const nyitva = nyitott.includes(kulcs);
          const allapot = ALLAPOTOK[h.allapot] ?? ALLAPOTOK.folyamatban;
          const Ikon = allapot.Ikon;
          return (
            <div
              key={kulcs}
              className={`rounded-[var(--radius)] border ${h.keses ? "border-text-danger/40" : "border-border"}`}
            >
              <div className="flex items-center gap-2 px-3 py-2.5">
                <button
                  type="button"
                  onClick={() => toggle(kulcs)}
                  aria-expanded={nyitva}
                  // flex-wrap: sok elem fér ebbe a sorba (badge, arány, összeg,
                  // határidő) - keskeny (telefonos) képernyőn ez nem fér ki
                  // egy sorba, enélkül az utolsó elem (a határidő) levágódna.
                  className="flex flex-1 flex-wrap items-center gap-x-2 gap-y-1 text-left"
                >
                  {nyitva ? (
                    <ChevronDown size={14} className="shrink-0 text-text-muted" />
                  ) : (
                    <ChevronRight size={14} className="shrink-0 text-text-muted" />
                  )}
                  <span className="min-w-[130px] text-[13px] font-medium text-text-primary">{h.honap_szoveg}</span>

                  <span
                    className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${allapot.hatter} ${allapot.szin}`}
                  >
                    <Ikon size={11} />
                    {allapot.label}
                  </span>

                  <span className="text-[12px] text-text-secondary">
                    {h.kesz + h.kihagyva}/{h.osszes} rendben
                    {h.hianyzo > 0 && <span className="text-text-warning"> · {h.hianyzo} hiányzik</span>}
                  </span>

                  {h.brutto_osszesen != null && (
                    <span className="text-[12px] text-text-muted">{formatFt(h.brutto_osszesen)}</span>
                  )}

                  <span className="ml-auto flex items-center gap-1.5 whitespace-nowrap text-[11px]">
                    {h.keses ? (
                      <span className="flex items-center gap-1 text-text-danger">
                        <AlertTriangle size={11} />
                        Határidő lejárt: {huDatum(h.hatarido)}
                      </span>
                    ) : (
                      <span className="text-text-muted">Határidő: {huDatum(h.hatarido)}</span>
                    )}
                  </span>
                </button>

                <Link
                  href={`/belsos-tig?ev=${h.ev}&honap=${h.honap}`}
                  className="shrink-0 rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3"
                >
                  Megnyitás
                </Link>
              </div>

              {nyitva && (
                <div className="border-t border-border px-3 py-2">
                  {h.teendok.length === 0 ? (
                    <p className="text-[12px] text-text-success">
                      Ez a hónap kész: minden belsős munkatárs TIG-je kiküldve (vagy kihagyva), a számlák feltöltve és
                      kifizetve.
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                    <table className="os-table min-w-full border-collapse text-[12px]">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="py-1 pr-4 text-left font-medium text-text-secondary">Kinek</th>
                          <th className="py-1 pr-4 text-left font-medium text-text-secondary">Mi hiányzik</th>
                          <th className="py-1 text-right font-medium text-text-secondary">Mikorra</th>
                        </tr>
                      </thead>
                      <tbody>
                        {h.teendok.map((t) => (
                          <tr key={t.employee_id} className="border-b border-border last:border-0">
                            <td className="py-1.5 pr-4">
                              <Link href={`/csapat/${t.employee_id}`} className="text-text-accent hover:underline">
                                {t.full_name}
                              </Link>
                            </td>
                            <td className="py-1.5 pr-4 text-text-secondary">{t.hianyzik}</td>
                            <td className={`py-1.5 text-right whitespace-nowrap ${h.keses ? "text-text-danger" : "text-text-muted"}`}>
                              {huDatum(h.hatarido)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
