import { Campaign, ENTITY_PATHS, formatDate, getCampaigns } from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";

export default async function KampanyokPage() {
  const campaigns = await getCampaigns();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Kampányok (${campaigns.length})`}>
          <DataTable<Campaign>
            rows={campaigns}
            emptyText="Még nincs felvett kampány - importáld a Notionból, vagy adj hozzá egyet a /api/v1/campaigns végponton."
            getHref={(c) => `/kampanyok/${c.id}`}
            deleteHref={(c) => `${ENTITY_PATHS.campaign}/${c.id}`}
            filterable
            columns={[
              { header: "Név", render: (c) => c.nev, sortAccessor: (c) => c.nev },
              {
                header: "Státusz",
                render: (c) => (c.kampany_statusza ? <StatusBadge label={c.kampany_statusza} tone="neutral" /> : "–"),
                sortAccessor: (c) => c.kampany_statusza,
              },
              { header: "Határidő", render: (c) => formatDate(c.hatarido), sortAccessor: (c) => c.hatarido },
              {
                header: "Kész",
                align: "right",
                render: (c) => <StatusBadge label={c.kesz ? "Kész" : "Folyamatban"} tone={c.kesz ? "success" : "warning"} />,
                sortAccessor: (c) => (c.kesz ? 1 : 0),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
