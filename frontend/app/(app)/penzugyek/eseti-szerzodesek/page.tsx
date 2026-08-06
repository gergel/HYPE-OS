import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StopClickPropagation } from "@/components/StopClickPropagation";
import { TopBar } from "@/components/TopBar";
import { formatDate, formatHuf, getEsetiSzerzodesek, type EsetiSzerzodes } from "@/lib/api";

/** Eseti szerződések: MINDEN alvállalkozói eseti megbízási szerződés egy
 * listában, mellette az EMBER és a PROJEKT, amihez tartozik.
 *
 * Eddig csak szétszórva lehetett rájuk látni: projektenként az Utókövetésen,
 * emberenként a munkatárs adatlapján. Az álló keretszerződések nincsenek itt -
 * azoknak külön fülük van (lásd /penzugyek/keretszerzodesek, illetve backend
 * models/contract.py Contract.keretszerzodes).
 *
 * Projekt nélküli sor is lehet köztük: a munkatárs Notion-lapjáról átvett
 * szerződések nincsenek egyetlen projekthez sem kötve. */
export default async function EsetiSzerzodesekPage() {
  const rows = await getEsetiSzerzodesek();
  const alairtak = rows.filter((s) => s.alairva || s.szerzodes_file_url).length;
  const osszesNetto = rows.reduce((sum, s) => sum + (s.netto_osszeg ?? 0), 0);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Eseti szerződések (${rows.length})`}>
          <p className="mb-3 text-[12.5px] text-text-muted">
            Minden alvállalkozói eseti megbízási szerződés, azzal együtt, hogy melyik emberhez és melyik projekthez
            tartozik. {alairtak} szerződésnél van meg az aláírt papír. Összesen {formatHuf(osszesNetto)} nettó. Az álló
            keretszerződések a <a href="/penzugyek/keretszerzodesek" className="text-text-accent hover:underline">
              Keretszerződések
            </a>{" "}
            fülön vannak.
          </p>
          <DataTable<EsetiSzerzodes>
            filterable
            rows={rows}
            emptyText="Még nincs eseti megbízási szerződés."
            getHref={(s) => `/szerzodesek/${s.id}`}
            columns={[
              {
                header: "Munkatárs",
                render: (s) =>
                  s.employee_id ? (
                    <StopClickPropagation>
                      <a href={`/csapat/${s.employee_id}`} className="text-text-accent hover:underline">
                        {s.employee_nev ?? `#${s.employee_id}`}
                      </a>
                    </StopClickPropagation>
                  ) : (
                    <span className="text-text-muted">Nincs megbízott</span>
                  ),
                sortAccessor: (s) => s.employee_nev,
              },
              {
                // A projektkód is kell: a projekt neve önmagában sokszor
                // ismétlődik (ugyanaz a forgatás több kóddal is fut).
                header: "Projekt",
                render: (s) =>
                  s.project_id ? (
                    <StopClickPropagation>
                      <a href={`/projektek/${s.project_id}`} className="text-text-accent hover:underline">
                        {s.projektkod ? `${s.projektkod} – ` : ""}
                        {s.project_nev ?? `#${s.project_id}`}
                      </a>
                    </StopClickPropagation>
                  ) : (
                    <span className="text-text-muted">Nincs projekthez kötve</span>
                  ),
                sortAccessor: (s) => `${s.projektkod ?? ""} ${s.project_nev ?? ""}`.trim(),
              },
              { header: "Cég neve", render: (s) => s.ceg_neve ?? "–", sortAccessor: (s) => s.ceg_neve },
              {
                header: "Megbízás tárgya",
                render: (s) => s.megbizas_targya ?? "–",
                sortAccessor: (s) => s.megbizas_targya,
              },
              {
                header: "Nettó",
                align: "right",
                render: (s) => (s.netto_osszeg === null ? "–" : formatHuf(s.netto_osszeg)),
                sortAccessor: (s) => s.netto_osszeg,
              },
              {
                header: "Teljesítés",
                render: (s) => s.teljesites_szoveg ?? "–",
                sortAccessor: (s) => s.teljesites_szoveg,
              },
              {
                header: "Állapot",
                render: (s) => s.szerzodes_allapota ?? <span className="text-text-muted">Nincs állapot</span>,
                sortAccessor: (s) => s.szerzodes_allapota,
              },
              {
                header: "Keltezés",
                align: "right",
                render: (s) => formatDate(s.keltezes),
                sortAccessor: (s) => s.keltezes,
              },
              {
                // Maga a papír: ha van feltöltött/generált fájl, innen egy
                // kattintással megnyitható (a sor kattintása az adatlapra visz).
                header: "Szerződés",
                align: "right",
                render: (s) =>
                  s.szerzodes_file_url ? (
                    <StopClickPropagation>
                      <a
                        href={s.szerzodes_file_url}
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
        </Card>
      </div>
    </div>
  );
}
