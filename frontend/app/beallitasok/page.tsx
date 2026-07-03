import { AccountCard } from "@/components/AccountCard";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { Employee, getEmployees } from "@/lib/api";

const ROLE_LABEL: Record<string, string> = {
  admin: "Admin",
  operator: "Operatőr",
  editor: "Vágó",
  client: "Ügyfél",
};

export default async function BeallitasokPage() {
  const employees = await getEmployees();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <AccountCard />

        <Card title={`Csapattagok és szerepkörök (${employees.length})`}>
          <DataTable<Employee>
            rows={employees}
            emptyText="Még nincs felvett crew tag."
            getHref={(e) => `/csapat/${e.id}`}
            columns={[
              { header: "Név", render: (e) => e.full_name },
              { header: "Email", render: (e) => e.email ?? "–" },
              { header: "Szerepkör", render: (e) => <StatusBadge label={ROLE_LABEL[e.role] ?? e.role} tone="neutral" /> },
              {
                header: "Aktív",
                align: "right",
                render: (e) => <StatusBadge label={e.is_active ? "Aktív" : "Inaktív"} tone={e.is_active ? "success" : "neutral"} />,
              },
            ]}
          />
        </Card>

        <Card title="Rendszer">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            <div>
              <dt className="text-[12px] text-text-muted">API cím</dt>
              <dd className="mt-0.5 text-[13px] text-text-primary">{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}</dd>
            </div>
            <div>
              <dt className="text-[12px] text-text-muted">Adatforrás</dt>
              <dd className="mt-0.5 text-[13px] text-text-primary">Notion import (idempotens, egyenkénti mezőleképezéssel)</dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  );
}
