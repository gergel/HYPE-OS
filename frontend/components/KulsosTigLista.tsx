"use client";

import { useState } from "react";
import { DataTable } from "@/components/DataTable";
import { KulsosTigModal } from "@/components/KulsosTigModal";
import { StatusBadge } from "@/components/StatusBadge";
import { StopClickPropagation } from "@/components/StopClickPropagation";
import type { KulsosTig } from "@/lib/api";
import { datum } from "@/lib/utokovetes";
import { formatFt } from "@/lib/ido";

/** A külsős TIG-ek táblázata, felugró ablakkal.
 *
 * Azért külön (kliens) komponens az oldaltól: a sorra kattintás állapotot
 * tart (melyik TIG van nyitva), amit szerver komponens nem tud - viszont maga
 * az adatlekérés maradhat a szerveren. */
export function KulsosTigLista({ rows }: { rows: KulsosTig[] }) {
  const [nyitottTig, setNyitottTig] = useState<number | null>(null);

  return (
    <>
            <DataTable<KulsosTig>
              filterable
              rows={rows}
              emptyText="Még nincs külsős teljesítési igazolás."
              // A sor MAGÁT A TIG-ET nyitja meg felugró ablakban: pont az az
              // egy papír érdekes, nem a projekt összes papírja. A getHref azért
              // marad meg mellette, hogy Ctrl+kattintással a projekt
              // utókövetése új fülön is nyitható legyen.
              getHref={(t) => (t.project_id ? `/utokovetes/${t.project_id}` : "/utokovetes")}
              onRowClick={setNyitottTig}
              columns={[
                {
                  // A TIG MÁSIK OLDALA: a számlázó fél, akinek a nevére szól -
                  // ember vagy cég. Alatta, hogy kinek a munkáját igazolja, ha
                  // az nem ugyanaz (más nevében is számlázhat).
                  header: "Kinek a nevére",
                  render: (t) => (
                    <span>
                      {t.vallalkozas_id ? (
                        <StopClickPropagation>
                          <a href="/penzugyek/vallalkozasok" className="text-text-accent hover:underline">
                            {t.vallalkozas_nev ?? `#${t.vallalkozas_id}`}
                          </a>
                        </StopClickPropagation>
                      ) : t.employee_id ? (
                        <StopClickPropagation>
                          <a href={`/csapat/${t.employee_id}`} className="text-text-accent hover:underline">
                            {t.employee_nev ?? `#${t.employee_id}`}
                          </a>
                        </StopClickPropagation>
                      ) : (
                        <span className="text-text-muted">Nincs megbízott</span>
                      )}
                      {t.lefedettek.length > 0 && t.lefedettek.join(", ") !== (t.employee_nev ?? "") && (
                        <span className="block text-[11px] text-text-muted">{t.lefedettek.join(", ")} munkájáért</span>
                      )}
                    </span>
                  ),
                  sortAccessor: (t) => t.vallalkozas_nev ?? t.employee_nev,
                },
                {
                  header: "Projekt",
                  render: (t) => (
                    <span>
                      {t.project_id ? (
                        <StopClickPropagation>
                          <a href={`/projektek/${t.project_id}`} className="text-text-accent hover:underline">
                            {t.projektkod ? `${t.projektkod} – ` : ""}
                            {t.project_nev ?? `#${t.project_id}`}
                          </a>
                        </StopClickPropagation>
                      ) : (
                        <span className="text-text-muted">Nincs projekt</span>
                      )}
                      {/* Egy TIG több forgatást is igazolhat egy papíron. */}
                      {t.projektek_szama > 1 && (
                        <span className="block text-[11px] text-text-muted">
                          + még {t.projektek_szama - 1} projekt ugyanezen a papíron
                        </span>
                      )}
                    </span>
                  ),
                  sortAccessor: (t) => `${t.projektkod ?? ""} ${t.project_nev ?? ""}`.trim(),
                },
                {
                  header: "Forgatás",
                  render: (t) => datum(t.forgatas_datuma),
                  sortAccessor: (t) => t.forgatas_datuma,
                },
                {
                  header: "Nettó",
                  align: "right",
                  render: (t) => (t.netto_osszeg === null ? "–" : formatFt(t.netto_osszeg)),
                  sortAccessor: (t) => t.netto_osszeg,
                },
                {
                  header: "Teljesítés",
                  render: (t) => t.teljesites_szoveg ?? "–",
                  sortAccessor: (t) => t.teljesites_szoveg,
                },
                {
                  // A kihagyás INDOKA a jelölés alatt: egy "Kihagyva" sor
                  // magyarázat nélkül pont azt a kérdést hagyná nyitva, ami miatt
                  // az ember ránéz a listára.
                  header: "Állapot",
                  render: (t) => (
                    <span>
                      {t.allapot === "Kihagyva" ? (
                        <StatusBadge label="Kihagyva" tone="neutral" />
                      ) : t.allapot === "Kiküldve" ? (
                        <StatusBadge label="Kiküldve" tone="success" />
                      ) : (
                        <StatusBadge label={t.allapot ?? "Készítés alatt"} tone="warning" />
                      )}
                      {t.kihagyas_oka && (
                        <span className="mt-1 block max-w-[18rem] text-[11px] text-text-muted">{t.kihagyas_oka}</span>
                      )}
                    </span>
                  ),
                  sortAccessor: (t) => t.allapot,
                },
                {
                  header: "Számla",
                  render: (t) =>
                    t.szamla_kifizetve ? (
                      <StatusBadge label="Kifizetve" tone="success" />
                    ) : t.szamla_db > 0 ? (
                      <StatusBadge label={`${t.szamla_db} db, nincs kifizetve`} tone="warning" />
                    ) : (
                      <span className="text-text-muted">Nincs számla</span>
                    ),
                  sortAccessor: (t) => (t.szamla_kifizetve ? 2 : t.szamla_db > 0 ? 1 : 0),
                },
                {
                  header: "Keltezés",
                  align: "right",
                  render: (t) => datum(t.keltezes),
                  sortAccessor: (t) => t.keltezes,
                },
                {
                  header: "TIG",
                  align: "right",
                  render: (t) =>
                    t.file_url ? (
                      <StopClickPropagation>
                        <a
                          href={t.file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-text-accent hover:underline"
                        >
                          Megnyitás
                        </a>
                      </StopClickPropagation>
                    ) : (
                      <span className="text-text-muted">Nincs fájl</span>
                    ),
                },
              ]}
            />
      {nyitottTig !== null && <KulsosTigModal tigId={nyitottTig} onClose={() => setNyitottTig(null)} />}
    </>
  );
}
