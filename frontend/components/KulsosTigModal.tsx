"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ModalReteg } from "@/components/ModalReteg";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { formatFt } from "@/lib/ido";
import type { KulsosTigReszlet } from "@/lib/api";

/** EGY külsős TIG adatlapja felugró ablakban.
 *
 * A listáról ide jutunk, és szándékosan nem a projekt utókövetés-oldalára: ott
 * a projekt ÖSSZES papírja van, itt viszont pont az a kérdés, hogy ennek az egy
 * embernek erre az egy projektre mi van a papírján - összeg, teljesítés,
 * cégadat, és hogy kinek a munkáját fedi.
 *
 * A tartalmat a megnyitáskor kérjük le (`/kulsos-tigek/{id}`), nem a listával
 * együtt: a lista több száz sor lehet, oda nem kell minden mező és minden
 * kapcsolt rekord.
 *
 * Ez a nézet OLVASÓ: a szerkesztés (állapot, összeg, újraküldés, törlés) a
 * projekt utókövetés-oldalán van, ahová innen egy gomb visz - kettőzött
 * szerkesztő-felületből előbb-utóbb két, egymástól elcsúszó igazság lenne. */
export function KulsosTigModal({ tigId, onClose }: { tigId: number; onClose: () => void }) {
  const [adat, setAdat] = useState<KulsosTigReszlet | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  // A hívó FELTÉTELESEN rendereli ({nyitott !== null && <KulsosTigModal .../>}),
  // ezért minden megnyitás friss példány, üres állapottal - nem kell "nyitáskor
  // üríts" lépés az effektben, ami fölösleges újrarenderelést okozna.
  useEffect(() => {
    let ervenyes = true;
    authFetch(`/api/v1/kulsos-tigek/${tigId}`)
      .then(async (res) => {
        if (!ervenyes) return;
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          setHiba(detail?.detail ?? `Nem sikerült betölteni (HTTP ${res.status})`);
          return;
        }
        setAdat((await res.json()) as KulsosTigReszlet);
      })
      .catch((err) => ervenyes && setHiba(`Nem sikerült betölteni: ${err}`));
    // Egy gyors kattintás-sorozatnál a KORÁBBI kérés válasza is megérkezhet,
    // miután már másik sort nyitottunk - ez a jelző dobja el a késői választ.
    return () => {
      ervenyes = false;
    };
  }, [tigId]);

  // Escape-re záródjon, és amíg nyitva van, a háttér ne görgethessen.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const elozo = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = elozo;
    };
  }, [onClose]);

  return (
    <ModalReteg onClose={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-3xl rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-3">
          <span className="text-[13px] text-text-secondary">Teljesítési igazolás</span>
          <div className="flex items-center gap-2">
            {adat?.project_id && (
              <Link href={`/utokovetes/${adat.project_id}`} className="btn btn-ghost !text-[12px]">
                Szerkesztés az utókövetésen →
              </Link>
            )}
            <button type="button" onClick={onClose} className="btn btn-ghost !text-[12px]">
              Bezárás
            </button>
          </div>
        </div>

        <div className="max-h-[75vh] overflow-y-auto p-5">
          {hiba ? (
            <p className="text-[13px] text-text-danger">{hiba}</p>
          ) : adat === null ? (
            <p className="text-[13px] text-text-muted">Betöltés…</p>
          ) : (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-3">
                <h3 className="text-[15px] font-medium text-text-primary">
                  {adat.vallalkozas_nev ?? adat.employee_nev ?? "Nincs megbízott"}
                </h3>
                {adat.allapot === "Kihagyva" ? (
                  <StatusBadge label="Kihagyva" tone="neutral" />
                ) : adat.allapot === "Kiküldve" ? (
                  <StatusBadge label="Kiküldve" tone="success" />
                ) : (
                  <StatusBadge label={adat.allapot ?? "Készítés alatt"} tone="warning" />
                )}
                {adat.szamla_kifizetve && <StatusBadge label="Számla kifizetve" tone="success" />}
              </div>

              {/* A kihagyás indoka kiemelten: ez a listán is látszik, de itt ez
                  a legfontosabb információ a papírról - más ugyanis nincs rajta. */}
              {adat.kihagyas_oka && (
                <div className="rounded-[var(--radius)] border border-border bg-surface-3 p-3">
                  <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                    A kihagyás oka
                  </p>
                  <p className="text-[13px] text-text-primary">{adat.kihagyas_oka}</p>
                </div>
              )}

              <Adatsorok
                sorok={[
                  ["Projekt", adat.project_nev ? `${adat.projektkod ? `${adat.projektkod} – ` : ""}${adat.project_nev}` : "–"],
                  ["Forgatás", adat.forgatas_datuma ?? "–"],
                  ["Megbízás tárgya", adat.megbizas_targya ?? "–"],
                  ["Teljesítés ideje", adat.teljesites_szoveg ?? "–"],
                  ["Keltezés", adat.keltezes ?? "–"],
                  [
                    "Nettó",
                    adat.netto_osszeg === null
                      ? "–"
                      : `${formatFt(adat.netto_osszeg)}${adat.plusz_afa ? " + ÁFA" : ""}`,
                  ],
                  ["Bruttó", adat.brutto_osszeg === null ? "–" : formatFt(adat.brutto_osszeg)],
                  ["Cég neve", adat.ceg_neve ?? "–"],
                  ["Székhely", adat.szekhely ?? "–"],
                  ["Adószám", adat.adoszam ?? "–"],
                  ["E-mail", adat.email ?? "–"],
                ]}
              />

              {/* Kinek a munkáját igazolja - egy papír több embert és több
                  forgatást is lefedhet (lásd backend
                  models/performance_certificate.py PerformanceCertificateTetel). */}
              <div>
                <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                  Kinek a munkáját igazolja
                </p>
                {adat.tetelek.length === 0 ? (
                  <p className="text-[12.5px] text-text-muted">
                    Nincs tételes bontás - a papír a saját projektjén a saját emberét fedi.
                    {adat.lefedettek.length > 0 && ` (${adat.lefedettek.join(", ")})`}
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="os-table min-w-full border-collapse text-[12.5px]">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="py-1 pr-4 text-left font-medium text-text-muted">Ki</th>
                          <th className="py-1 pr-4 text-left font-medium text-text-muted">Melyik projekten</th>
                          <th className="py-1 text-right font-medium text-text-muted">Ebből az övé</th>
                        </tr>
                      </thead>
                      <tbody>
                        {adat.tetelek.map((t, i) => (
                          <tr key={`${t.project_id}-${t.employee_id}-${i}`} className="border-b border-border last:border-0">
                            <td className="py-1.5 pr-4 text-text-primary">{t.employee_nev ?? `#${t.employee_id}`}</td>
                            <td className="py-1.5 pr-4 text-text-secondary">
                              {t.projektkod ? `${t.projektkod} – ` : ""}
                              {t.project_nev ?? `#${t.project_id}`}
                              {t.forgatas_datuma && (
                                <span className="ml-2 text-[11px] text-text-muted">{t.forgatas_datuma}</span>
                              )}
                            </td>
                            <td className="py-1.5 text-right tabular-nums text-text-secondary">
                              {/* Szándékosan üres is lehet: a bontás nem mindig
                                  ismert, és tippelt számot nem írunk a papírra. */}
                              {t.netto_osszeg === null ? "–" : formatFt(t.netto_osszeg)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-4">
                <div>
                  <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">A TIG papírja</p>
                  {adat.file_url ? (
                    <a
                      href={adat.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[13px] text-text-accent hover:underline"
                    >
                      Megnyitás
                    </a>
                  ) : (
                    <p className="text-[12.5px] text-text-muted">Nincs fájl</p>
                  )}
                </div>
                <div>
                  <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">Számlák</p>
                  {adat.szamlak.length === 0 ? (
                    <p className="text-[12.5px] text-text-muted">Nincs feltöltött számla</p>
                  ) : (
                    <ul className="space-y-0.5">
                      {adat.szamlak.map((f) => (
                        <li key={f.id}>
                          <a
                            href={f.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[13px] text-text-accent hover:underline"
                          >
                            {f.filename}
                          </a>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </ModalReteg>
  );
}

function Adatsorok({ sorok }: { sorok: [string, string][] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
      {sorok.map(([cimke, ertek]) => (
        <div key={cimke} className="flex justify-between gap-3 border-b border-border pb-1.5">
          <dt className="text-[12px] text-text-muted">{cimke}</dt>
          <dd className="text-right text-[12.5px] text-text-primary">{ertek}</dd>
        </div>
      ))}
    </dl>
  );
}
