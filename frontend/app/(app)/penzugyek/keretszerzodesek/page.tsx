import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { TopBar } from "@/components/TopBar";
import { KeretszerzodesAddWidget } from "@/components/KeretszerzodesAddWidget";
import { StopClickPropagation } from "@/components/StopClickPropagation";
import { ENTITY_PATHS, formatDate, getContracts, getEmployees, type Contract } from "@/lib/api";

type KeretszerzodesRow = Contract & { employee_name: string };

/** Van-e a bejegyzés mögött tényleg keretszerződés?
 *
 * A Notion-import minden munkatárs lapjáról áthozza a cégadatot (cégnév,
 * székhely, adószám), ezért sokaknál keletkezett olyan sor, ami mögött nincs
 * megkötött keretszerződés - csak a vállalkozás adatai. Keretszerződése annak
 * van, akinél megvan az aláírt papír vagy legalább a szerződés állapota (a
 * kézzel felvett bejegyzés is kap egyet: "Aktív"). */
function vanKeretszerzodes(c: Contract): boolean {
  return Boolean(c.alairva || c.szerzodes_file_url || c.szerzodes_allapota);
}

/** Keretszerződések: a KÜLSŐS munkatársakhoz tartozó álló megbízási
 * szerződések - ezek NEM egy konkrét projekthez kötöttek
 * (Contract.project_id == null), ezért az utókövetés nem kér tőlük
 * projektenként eseti szerződést.
 *
 * Csak külsősök, és csak akiknek tényleg van keretszerződésük: a belsősöknél a
 * havi bérelszámolás és a belsős TIG fedi le ugyanezt. */
export default async function KeretszerzodesekPage() {
  const [contracts, employees] = await Promise.all([getContracts(), getEmployees()]);
  const employeeById = new Map(employees.map((e) => [e.id, e]));

  const rows: KeretszerzodesRow[] = contracts
    .filter((c) => {
      if (c.tipus !== "alvallalkozoi" || c.project_id || !c.employee_id) return false;
      if (employeeById.get(c.employee_id)?.tipus !== "kulsos") return false;
      return vanKeretszerzodes(c);
    })
    .map((c) => ({ ...c, employee_name: employeeById.get(c.employee_id as number)?.full_name ?? `#${c.employee_id}` }));

  // Felvenni azt a külsőst lehet, akinél még nincs (valódi) keretszerződés - a
  // cégadat-only bejegyzést a backend előlépteti, nem duplikálja (lásd
  // routes/contracts.py create_keretszerzodes). Belsőst nem ajánlunk.
  const linkedEmployeeIds = new Set(rows.map((r) => r.employee_id));
  const candidates = employees.filter((e) => e.tipus === "kulsos" && !linkedEmployeeIds.has(e.id));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Keretszerződések (${rows.length})`}>
          <KeretszerzodesAddWidget candidates={candidates} />
          <DataTable<KeretszerzodesRow>
            filterable
            rows={rows}
            emptyText="Még nincs felvett keretszerződés."
            getHref={(c) => `/csapat/${c.employee_id}`}
            deleteHref={(c) => `${ENTITY_PATHS.contract}/${c.id}`}
            columns={[
              { header: "Munkatárs", render: (c) => c.employee_name, sortAccessor: (c) => c.employee_name },
              { header: "Cég neve", render: (c) => c.ceg_neve ?? "–", sortAccessor: (c) => c.ceg_neve },
              { header: "Adószám", render: (c) => c.adoszam ?? "–", sortAccessor: (c) => c.adoszam },
              {
                header: "Állapot",
                render: (c) => c.szerzodes_allapota ?? "–",
                sortAccessor: (c) => c.szerzodes_allapota,
              },
              {
                header: "Keltezés",
                align: "right",
                render: (c) => formatDate(c.keltezes),
                sortAccessor: (c) => c.keltezes,
              },
              {
                // A szerződés saját adatlapja: itt tölthető fel és nézhető meg
                // az aláírt PDF (a sor kattintása a munkatárshoz visz, ezért
                // ez a link megállítja a sor-navigációt).
                header: "Dokumentumok",
                align: "right",
                render: (c) => (
                  <StopClickPropagation>
                    <a href={`/szerzodesek/${c.id}`} className="text-text-accent hover:underline">
                      Fájlok
                    </a>
                  </StopClickPropagation>
                ),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
