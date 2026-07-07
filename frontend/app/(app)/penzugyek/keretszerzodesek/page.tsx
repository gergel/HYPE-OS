import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { TopBar } from "@/components/TopBar";
import { KeretszerzodesAddWidget } from "@/components/KeretszerzodesAddWidget";
import { ENTITY_PATHS, formatDate, getContracts, getEmployees, type Contract } from "@/lib/api";

type KeretszerzodesRow = Contract & { employee_name: string };

/** Keretszerződések: a crew-tagokhoz (akár belsős, akár külsős) tartozó álló
 * megbízási szerződések - ezek NEM egy konkrét projekthez kötöttek
 * (Contract.project_id == null), ezért az "Alvállalkozók szerződése" nézet
 * kihagyja azokat, akiknek itt már van bejegyzésük (nincs szükség eseti
 * szerződésre projektenként). */
export default async function KeretszerzodesekPage() {
  const [contracts, employees] = await Promise.all([getContracts(), getEmployees()]);
  const employeeById = new Map(employees.map((e) => [e.id, e]));

  const rows: KeretszerzodesRow[] = contracts
    .filter((c) => c.tipus === "alvallalkozoi" && !c.project_id && c.employee_id)
    .map((c) => ({ ...c, employee_name: employeeById.get(c.employee_id as number)?.full_name ?? `#${c.employee_id}` }));

  const linkedEmployeeIds = new Set(rows.map((r) => r.employee_id));
  const candidates = employees.filter((e) => !linkedEmployeeIds.has(e.id));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Keretszerződések (${rows.length})`}>
          <KeretszerzodesAddWidget candidates={candidates} />
          <DataTable<KeretszerzodesRow>
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
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
