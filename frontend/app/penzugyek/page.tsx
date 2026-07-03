import { ENTITY_PATHS, Expense, formatHuf, getExpenses, getRevenues, Revenue } from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";

export default async function PenzugyekPage() {
  const [expenses, revenues] = await Promise.all([getExpenses(), getRevenues()]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <Card title={`Kiadások (${expenses.length})`}>
          <DataTable<Expense>
            rows={expenses}
            emptyText="Még nincs felvett kiadás - importáld a Notionból, vagy adj hozzá egyet a /api/v1/expenses végponton."
            getHref={(e) => `/penzugyek/kiadas/${e.id}`}
            deleteHref={(e) => `${ENTITY_PATHS.expense}/${e.id}`}
            filterable
            columns={[
              { header: "Megnevezés", render: (e) => e.megnevezes, sortAccessor: (e) => e.megnevezes },
              { header: "Típus", render: (e) => e.tipus ?? "–", sortAccessor: (e) => e.tipus },
              { header: "Nettó", align: "right", render: (e) => formatHuf(e.netto), sortAccessor: (e) => e.netto },
              { header: "Bruttó", align: "right", render: (e) => formatHuf(e.brutto), sortAccessor: (e) => e.brutto },
              {
                header: "Kész",
                align: "right",
                render: (e) => <StatusBadge label={e.kesz ? "Kifizetve" : "Nyitott"} tone={e.kesz ? "success" : "warning"} />,
                sortAccessor: (e) => (e.kesz ? 1 : 0),
              },
            ]}
          />
        </Card>

        <Card title={`Bevételek (${revenues.length})`}>
          <DataTable<Revenue>
            rows={revenues}
            emptyText="Még nincs felvett bevétel - importáld a Notionból, vagy adj hozzá egyet a /api/v1/revenues végponton."
            getHref={(r) => `/penzugyek/bevetel/${r.id}`}
            deleteHref={(r) => `${ENTITY_PATHS.revenue}/${r.id}`}
            filterable
            columns={[
              { header: "Forma", render: (r) => r.bevetel_formaja ?? "–", sortAccessor: (r) => r.bevetel_formaja },
              { header: "Nettó", align: "right", render: (r) => formatHuf(r.netto), sortAccessor: (r) => r.netto },
              { header: "Bruttó", align: "right", render: (r) => formatHuf(r.brutto), sortAccessor: (r) => r.brutto },
              { header: "Pénznem", align: "right", render: (r) => r.penznem, sortAccessor: (r) => r.penznem },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
