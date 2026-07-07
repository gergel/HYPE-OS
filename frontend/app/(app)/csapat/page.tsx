import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { Employee, ENTITY_PATHS, getEmployees } from "@/lib/api";

/** Külsős: a közös crew-adatbázisból (lásd Vágók/Belsősök oldal) azok, akik
 * sem nem belsősök, sem nem vágók/kreatívok/stáb - vagyis a diszpó-küldés
 * után eseti (nem keretszerződéses) megbízási szerződést igénylő emberek. Ha
 * valakit belsősre/vágóra sorolunk át (tipus mező), automatikusan eltűnik
 * innen és megjelenik a másik nézetben - ugyanaz a tábla, csak szűrve. */
export default async function CsapatPage() {
  const employees = await getEmployees();
  const rows = employees.filter((e) => e.tipus === "kulsos");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Külsős (${rows.length})`}>
          <QuickCreateForm
            postPath={ENTITY_PATHS.employee}
            addLabel="+ Új külsős hozzáadása"
            presetFields={{ tipus: "kulsos" }}
            fields={[
              { name: "full_name", label: "Név", required: true },
              { name: "email", label: "Email" },
            ]}
          />
          <DataTable<Employee>
            rows={rows}
            emptyText="Még nincs felvett külsős munkatárs."
            getHref={(e) => `/csapat/${e.id}`}
            deleteHref={(e) => `${ENTITY_PATHS.employee}/${e.id}`}
            filterable
            columns={[
              { header: "Név", render: (e) => e.full_name, sortAccessor: (e) => e.full_name },
              { header: "Email", render: (e) => e.email ?? "–", sortAccessor: (e) => e.email },
              { header: "Telefon", render: (e) => e.telefon ?? "–", sortAccessor: (e) => e.telefon },
              {
                header: "Aktív",
                render: (e) => <StatusBadge label={e.is_active ? "Aktív" : "Inaktív"} tone={e.is_active ? "success" : "neutral"} />,
                sortAccessor: (e) => (e.is_active ? 1 : 0),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
