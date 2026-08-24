"use client";

import { useCallback, useEffect, useState } from "react";
import { KeretModositasok } from "@/components/megrendeloi/KeretModositasok";
import { ModalReteg } from "@/components/ModalReteg";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { formatFt } from "@/lib/ido";
import { datum } from "@/lib/utokovetes";
import type { MegrendeloiKeretPapir, MegrendeloiKeretReszletek } from "@/lib/api";

/** Egy papír állapotjelzője. Ugyanaz a szókészlet, mint a gyűjtőoldalakon -
 * ha itt mást mutatna, ugyanarról a papírról két történet szólna. */
function PapirJelzo({ papir, cimke }: { papir: MegrendeloiKeretPapir | null; cimke: string }) {
  if (papir === null) return <StatusBadge label={`Nincs ${cimke}`} tone="warning" />;
  if (papir.allapot === "Kihagyva") return <StatusBadge label="Kihagyva" tone="neutral" />;
  if (papir.allapot === "Van már papír") return <StatusBadge label="Van már papír" tone="success" />;
  if (papir.allapot === "Kiküldve")
    return papir.alairt_file_url ? (
      <StatusBadge label="Kiküldve, aláírva" tone="success" />
    ) : (
      <StatusBadge label="Aláírásra vár" tone="warning" />
    );
  return <StatusBadge label={papir.allapot ?? "Készítés alatt"} tone="warning" />;
}

function PapirLink({ papir }: { papir: MegrendeloiKeretPapir | null }) {
  const url = papir?.alairt_file_url || papir?.file_url;
  if (!url) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="ml-2 text-[11.5px] text-text-accent hover:underline"
    >
      megnyitás
    </a>
  );
}

/** A keretszerződés ADATLAPJA felugró ablakban: a saját adatai, és minden
 * projekt, amit lefed - projektenként azzal együtt, hol tart a szerződése és a
 * teljesítési igazolása.
 *
 * Azért ez a nézet kell, mert a keretszerződésnél pont az összefüggés a kérdés:
 * mire használjuk ezt a keretet, és hol tart alatta a papírozás. A listasorból
 * csak az látszott, hogy "3 projektkódnál használjuk" - hogy melyik háromnál és
 * mi a helyzet velük, sehol.
 *
 * A PROJEKTKÓDOK papírjai tekintetében a nézet OLVASÓ: azokat a projektkód
 * adatlapján lehet szerkeszteni, ahová innen egy kattintással el lehet jutni.
 * Két helyen szerkeszthető ugyanaz a papír előbb-utóbb két különböző
 * viselkedést jelentene.
 *
 * A SZERZŐDÉSMÓDOSÍTÁS viszont itt intézhető, mert az magához a kerethez
 * tartozik - nincs másik hely, ahol dolga lenne. */
export function KeretszerzodesModal({
  keretId,
  onClose,
  canCreate = false,
  canEdit = false,
  canDelete = false,
}: {
  keretId: number;
  onClose: () => void;
  canCreate?: boolean;
  canEdit?: boolean;
  canDelete?: boolean;
}) {
  const [adat, setAdat] = useState<MegrendeloiKeretReszletek | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  const betolt = useCallback(async () => {
    try {
      const res = await authFetch(`/api/v1/megrendeloi-keretszerzodesek/${keretId}`);
      if (!res.ok) throw new Error(`${res.status}`);
      setAdat(await res.json());
    } catch (err) {
      setHiba(String(err));
    }
  }, [keretId]);

  useEffect(() => {
    void betolt();
  }, [betolt]);

  return (
    <ModalReteg onClose={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className="max-h-[85vh] w-full max-w-4xl overflow-y-auto rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {hiba && <p className="p-5 text-[13px] text-text-danger">Nem sikerült betölteni: {hiba}</p>}
        {!adat && !hiba && <p className="p-5 text-[13px] text-text-muted">Betöltés…</p>}

        {adat && (
          <>
            <div className="border-b border-border px-5 py-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-[15px] font-medium text-text-primary">
                  {adat.ceg_neve ?? adat.client_nev ?? `#${adat.id}`}
                </h3>
                <span className="flex items-center gap-2">
                  {adat.ervenyes ? (
                    <StatusBadge label="Élő keret" tone="success" />
                  ) : (
                    <StatusBadge label="Nem élő" tone="neutral" />
                  )}
                  {adat.alairva ? (
                    <StatusBadge label="Aláírva" tone="success" />
                  ) : (
                    <StatusBadge label={adat.allapot ?? "Készítés alatt"} tone="warning" />
                  )}
                </span>
              </div>
              <p className="mt-1 text-[12.5px] text-text-muted">
                {[adat.adoszam, adat.szekhely, adat.kepviselo, adat.email].filter(Boolean).join(" · ") ||
                  "Nincs cégadat rögzítve"}
              </p>
              <p className="mt-0.5 text-[12.5px] text-text-muted">
                {adat.megbizas_targya ? `${adat.megbizas_targya} · ` : ""}
                Keltezés: {datum(adat.keltezes)}
              </p>
              {adat.megjegyzes && (
                <p className="mt-1 text-[12.5px] text-text-secondary">{adat.megjegyzes}</p>
              )}
              <div className="mt-2 flex flex-wrap gap-3 text-[12.5px]">
                {adat.file_url && (
                  <a href={adat.file_url} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                    Keretszerződés megnyitása
                  </a>
                )}
                {adat.alairt_file_url && (
                  <a
                    href={adat.alairt_file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-text-accent hover:underline"
                  >
                    Aláírt példány
                  </a>
                )}
              </div>
            </div>

            <KeretModositasok
              keret={adat}
              modositasok={adat.modositasok}
              canCreate={canCreate}
              canEdit={canEdit}
              canDelete={canDelete}
              onValtozas={betolt}
            />

            {/* MINDEN feltöltött fájl - nem csak a két nevesített mező. A
                Notion-import a lap összes fájlját áthozza, de eddig nem volt
                hova ránézni rájuk. */}
            {adat.fajlok.length > 0 && (
              <div className="border-b border-border px-5 py-4">
                <p className="mb-2 text-[13px] font-medium text-text-primary">
                  Feltöltött fájlok ({adat.fajlok.length})
                </p>
                <ul className="space-y-1">
                  {adat.fajlok.map((f) => (
                    <li key={f.id} className="text-[12.5px]">
                      <a
                        href={f.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-text-accent hover:underline"
                      >
                        {f.filename}
                      </a>
                      <span className="ml-2 text-[11.5px] text-text-muted">
                        {f.kategoria}
                        {f.feltoltve ? ` · ${f.feltoltve}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="p-5">
              <p className="mb-3 text-[13px] font-medium text-text-primary">
                Projektek a keret alatt ({adat.projektkodok.length})
              </p>

              {adat.projektkodok.length === 0 ? (
                <p className="text-[12.5px] text-text-muted">
                  Ehhez a keretszerződéshez még nincs projektkód kapcsolva.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="os-table min-w-full border-collapse text-[13px]">
                    <thead>
                      <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-text-muted">
                        <th className="py-2 pr-3 font-medium">Projektkód</th>
                        <th className="py-2 pr-3 font-medium">Dátum</th>
                        <th className="py-2 pr-3 text-right font-medium">Nettó</th>
                        <th className="py-2 pr-3 font-medium">Szerződés</th>
                        <th className="py-2 font-medium">TIG</th>
                      </tr>
                    </thead>
                    <tbody>
                      {adat.projektkodok.map((pk) => (
                        <tr key={pk.id} className="border-b border-border last:border-0 align-top">
                          <td className="py-2 pr-3">
                            <a
                              href={`/projektek/project-kodok/${pk.id}`}
                              className="text-text-accent hover:underline"
                            >
                              {pk.projektkod}
                            </a>
                            {pk.project_nev && (
                              <span className="block text-[11.5px] text-text-muted">{pk.project_nev}</span>
                            )}
                          </td>
                          <td className="py-2 pr-3 text-text-secondary">{datum(pk.datum)}</td>
                          <td className="py-2 pr-3 text-right text-text-secondary">
                            {pk.netto_osszeg === null ? "–" : formatFt(pk.netto_osszeg)}
                          </td>
                          <td className="py-2 pr-3">
                            {/* Ahol a kapcsolók szerint nincs papírozás, ott a
                                hiányzó papír nem hiányosság, hanem döntés. */}
                            {!pk.kell_papir ? (
                              <span className="text-[11.5px] text-text-muted">Nem kell papír</span>
                            ) : (
                              <>
                                <PapirJelzo papir={pk.szerzodes} cimke="szerződés" />
                                <PapirLink papir={pk.szerzodes} />
                                {pk.szerzodes?.kihagyas_oka && (
                                  <span className="mt-1 block max-w-[16rem] text-[11px] text-text-muted">
                                    {pk.szerzodes.kihagyas_oka}
                                  </span>
                                )}
                              </>
                            )}
                          </td>
                          <td className="py-2">
                            {!pk.kell_papir ? (
                              <span className="text-[11.5px] text-text-muted">Nem kell papír</span>
                            ) : (
                              <>
                                <PapirJelzo papir={pk.tig} cimke="TIG" />
                                <PapirLink papir={pk.tig} />
                                {pk.tig?.kihagyas_oka && (
                                  <span className="mt-1 block max-w-[16rem] text-[11px] text-text-muted">
                                    {pk.tig.kihagyas_oka}
                                  </span>
                                )}
                              </>
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
