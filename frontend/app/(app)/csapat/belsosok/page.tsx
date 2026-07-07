import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StopClickPropagation } from "@/components/StopClickPropagation";
import { TopBar } from "@/components/TopBar";
import { BelsosAddWidget } from "@/components/BelsosAddWidget";
import { EmployeeActiveToggle } from "@/components/VagoInlineFields";
import { ENTITY_PATHS, getEmployees } from "@/lib/api";

/** Belsősök: a crew-adatbázisból (külsős + belsős) azok, akiket az admin
 * belsősként jelölt meg (Employee.tipus == "belsos") - bármikor bővíthető a
 * teljes crew listából, ugyanúgy ahogy a Vágók oldal a tipus=="vago" szűrést
 * használja, csak itt van egy "hozzáadás" widget is, mert idesorolás admin
 * döntés, nem egy fix Notion-import-béli kategória. */
export default async function BelsosokPage() {
  const employees = await getEmployees();
  const rows = employees.filter((e) => e.tipus === "belsos");
  const candidates = employees.filter((e) => e.tipus !== "belsos");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Belsősök (${rows.length})`}>
          <BelsosAddWidget candidates={candidates} />
          <QuickCreateForm
            postPath={ENTITY_PATHS.employee}
            addLabel="+ Új belsős hozzáadása"
            presetFields={{ tipus: "belsos" }}
            fields={[
              { name: "full_name", label: "Név", required: true },
              { name: "email", label: "Email" },
            ]}
          />
          <DataTable<(typeof rows)[number]>
            rows={rows}
            emptyText="Még nincs belsősként megjelölt munkatárs - válassz valakit fent a crew listából."
            getHref={(e) => `/csapat/${e.id}?from=belsosok`}
            columns={[
              { header: "Név", render: (e) => e.full_name, sortAccessor: (e) => e.full_name },
              { header: "Email", render: (e) => e.email ?? "–", sortAccessor: (e) => e.email },
              {
                header: "Aktív",
                render: (e) => (
                  <StopClickPropagation>
                    <EmployeeActiveToggle employeeId={e.id} initialActive={e.is_active} />
                  </StopClickPropagation>
                ),
                sortAccessor: (e) => (e.is_active ? 1 : 0),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
