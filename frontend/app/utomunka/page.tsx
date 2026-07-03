import { Deliverable, ENTITY_PATHS, formatDate, getDeliverables } from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";

export default async function UtomunkaPage() {
  const deliverables = await getDeliverables();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Utómunka (${deliverables.length})`}>
          <DataTable<Deliverable>
            rows={deliverables}
            emptyText="Még nincs felvett vágandó anyag - importáld a Notionból, vagy adj hozzá egyet a /api/v1/deliverables végponton."
            getHref={(d) => `/utomunka/${d.id}`}
            deleteHref={(d) => `${ENTITY_PATHS.deliverable}/${d.id}`}
            filterable
            columns={[
              { header: "Anyag", render: (d) => d.projekt_neve, sortAccessor: (d) => d.projekt_neve },
              {
                header: "Állapot",
                render: (d) => (d.allapot ? <StatusBadge label={d.allapot} tone="neutral" /> : "–"),
                sortAccessor: (d) => d.allapot,
              },
              { header: "Határidő", render: (d) => formatDate(d.hatarido), sortAccessor: (d) => d.hatarido },
              {
                header: "Kiküldve",
                align: "right",
                render: (d) => (
                  <StatusBadge label={d.anyag_kikuldve ? "Kiküldve" : "Nincs kiküldve"} tone={d.anyag_kikuldve ? "success" : "warning"} />
                ),
                sortAccessor: (d) => (d.anyag_kikuldve ? 1 : 0),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
