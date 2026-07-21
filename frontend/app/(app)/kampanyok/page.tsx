import { Campaign, ENTITY_PATHS, formatDate, getCampaigns, getFieldTypes } from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";

export default async function KampanyokPage() {
  const [campaigns, fieldTypes] = await Promise.all([getCampaigns(), getFieldTypes("campaign")]);
  const statusOptions = fieldTypes.kampany_statusza?.options ?? [];

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
                render: (c) => (
                  <EditableStatusBadge
                    patchPath={`${ENTITY_PATHS.campaign}/${c.id}`}
                    field="kampany_statusza"
                    value={c.kampany_statusza}
                    options={statusOptions}
                  />
                ),
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
