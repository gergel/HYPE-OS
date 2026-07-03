import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { Employee, getEmployees } from "@/lib/api";

const TIPUS_LABEL: Record<string, string> = {
  belsos: "Belsős",
  kulsos: "Külsős",
  vago: "Vágó",
  kreativ: "Kreatív",
  stab: "Stáb",
};

export default async function CsapatPage() {
  const employees = await getEmployees();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Csapat (${employees.length})`}>
          <DataTable<Employee>
            rows={employees}
            emptyText="Még nincs felvett crew tag - importáld a Notionból, vagy adj hozzá egyet a /api/v1/crew végponton."
            getHref={(e) => `/csapat/${e.id}`}
            columns={[
              { header: "Név", render: (e) => e.full_name },
              {
                header: "Típus",
                render: (e) => <StatusBadge label={TIPUS_LABEL[e.tipus] ?? e.tipus} tone="neutral" />,
              },
              { header: "Email", render: (e) => e.email ?? "–" },
              { header: "Telefon", render: (e) => e.telefon ?? "–" },
              {
                header: "Aktív",
                render: (e) => <StatusBadge label={e.is_active ? "Aktív" : "Inaktív"} tone={e.is_active ? "success" : "neutral"} />,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
