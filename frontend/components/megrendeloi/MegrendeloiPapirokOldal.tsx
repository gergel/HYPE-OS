import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { StopClickPropagation } from "@/components/StopClickPropagation";
import { TopBar } from "@/components/TopBar";
import {
  formatDate,
  formatHuf,
  getCurrentUser,
  getMegrendeloiPapirok,
  getMyPagePermissions,
  type MegrendeloiPapir,
  type MegrendeloiPapirFajta,
} from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/projektek/project-kodok";

/** A megrendelői papírok GYŰJTŐ oldala - egy fajtából az összes, a
 * KIHAGYOTTAKKAL együtt.
 *
 * Ugyanaz a szerep, mint az alvállalkozói oldalon az Eseti szerződések és a
 * Külsős TIG-ek oldalé: eddig csak projektkódonként lehetett rájuk látni,
 * tehát arra a kérdésre, hogy "hol tart összességében a megrendelői
 * papírozás", nem volt hely, ahol válasz lett volna.
 *
 * A kihagyottak azért maradnak a listában, mert a kihagyás indoka is
 * információ: ha eltűnnének, csak annyi látszana, hogy "nincs papír", ami
 * hiányosságnak néz ki, nem döntésnek.
 *
 * A két oldal (szerződések / TIG-ek) ugyanez a komponens, mert a két papír
 * mezőkészlete azonos - két külön táblázatból előbb-utóbb két különböző
 * viselkedés lenne. */
export async function MegrendeloiPapirokOldal({
  fajta,
  cim,
  leiras,
}: {
  fajta: MegrendeloiPapirFajta;
  cim: string;
  leiras: string;
}) {
  const [rows, currentUser, pagePermissions] = await Promise.all([
    getMegrendeloiPapirok(fajta),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");

  const kikuldott = rows.filter((p) => p.allapot === "Kiküldve").length;
  const kihagyott = rows.filter((p) => p.allapot === "Kihagyva").length;
  const alairtak = rows.filter((p) => p.alairt_file_url).length;
  const varakozok = rows.filter((p) => p.alairasra_var).length;
  const osszesNetto = rows.reduce((sum, p) => sum + (p.netto_osszeg ?? 0), 0);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`${cim} (${rows.length})`}>
          <p className="mb-3 text-[12.5px] text-text-muted">
            {leiras} {kikuldott} kiküldve, ebből {varakozok} aláírásra vár, {alairtak} aláírva megvan, {kihagyott}{" "}
            kihagyva. Összesen {formatHuf(osszesNetto)} nettó. A kihagyottaknál az indok is itt látszik.
          </p>
          <DataTable<MegrendeloiPapir>
            filterable
            rows={rows}
            emptyText={`Még nincs ${cim.toLowerCase()}.`}
            getHref={(p) => `/projektek/project-kodok/${p.project_code_id}`}
            deleteHref={canDelete ? (p) => `/api/v1/megrendeloi-papirok/${fajta}/${p.id}` : undefined}
            columns={[
              {
                header: "Projektkód",
                render: (p) => (
                  <StopClickPropagation>
                    <a
                      href={`/projektek/project-kodok/${p.project_code_id}`}
                      className="text-text-accent hover:underline"
                    >
                      {p.projektkod ?? `#${p.project_code_id}`}
                    </a>
                  </StopClickPropagation>
                ),
                sortAccessor: (p) => p.projektkod,
              },
              { header: "Megrendelő", render: (p) => p.ceg_neve ?? "–", sortAccessor: (p) => p.ceg_neve },
              {
                header: "Megbízás tárgya",
                render: (p) => p.megbizas_targya ?? "–",
                sortAccessor: (p) => p.megbizas_targya,
              },
              {
                header: "Nettó",
                align: "right",
                render: (p) =>
                  p.netto_osszeg === null ? "–" : `${formatHuf(p.netto_osszeg)}${p.plusz_afa ? " + ÁFA" : ""}`,
                sortAccessor: (p) => p.netto_osszeg,
              },
              {
                header: "Teljesítés",
                render: (p) => p.teljesites_szoveg ?? "–",
                sortAccessor: (p) => p.teljesites_szoveg,
              },
              {
                header: "Állapot",
                render: (p) => (
                  <span>
                    {p.allapot === "Kihagyva" ? (
                      <StatusBadge label="Kihagyva" tone="neutral" />
                    ) : p.allapot === "Kiküldve" ? (
                      <StatusBadge
                        label={p.alairt_file_url ? "Kiküldve, aláírva" : "Kiküldve, aláírásra vár"}
                        tone={p.alairt_file_url ? "success" : "warning"}
                      />
                    ) : p.allapot === "Van már papír" ? (
                      <StatusBadge label="Van már papír" tone="success" />
                    ) : (
                      <StatusBadge label={p.allapot ?? "Készítés alatt"} tone="warning" />
                    )}
                    {p.kihagyas_oka && (
                      <span className="mt-1 block max-w-[18rem] text-[11px] text-text-muted">{p.kihagyas_oka}</span>
                    )}
                  </span>
                ),
                sortAccessor: (p) => p.allapot,
              },
              {
                header: "Keltezés",
                align: "right",
                render: (p) => formatDate(p.keltezes),
                sortAccessor: (p) => p.keltezes,
              },
              {
                // Maga a papír: ha van generált vagy feltöltött fájl, innen egy
                // kattintással megnyitható (a sor kattintása a projektkódra visz).
                header: "Papír",
                align: "right",
                render: (p) => (
                  <span className="whitespace-nowrap">
                    {p.file_url ? (
                      <StopClickPropagation>
                        <a
                          href={p.file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-text-accent hover:underline"
                        >
                          Megnyitás
                        </a>
                      </StopClickPropagation>
                    ) : (
                      <span className="text-text-muted">Nincs fájl</span>
                    )}
                    {p.alairt_file_url && (
                      <StopClickPropagation>
                        <a
                          href={p.alairt_file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-2 text-text-accent hover:underline"
                        >
                          Aláírt
                        </a>
                      </StopClickPropagation>
                    )}
                  </span>
                ),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
