import { Campaign, ENTITY_PATHS, formatDate, getCampaigns, getCurrentUser, getFieldTypes, getMyPagePermissions } from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/kampanyok";

export default async function KampanyokPage() {
  const [campaigns, fieldTypes, currentUser, pagePermissions] = await Promise.all([
    getCampaigns(),
    getFieldTypes("campaign"),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const statusOptions = fieldTypes.kampany_statusza?.options ?? [];
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Kampányok (${campaigns.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.campaign}
              addLabel="+ Új kampány hozzáadása"
              fields={[
                { name: "nev", label: "Név", required: true },
                { name: "hatarido", label: "Határidő", type: "date" },
              ]}
            />
          )}
          <DataTable<Campaign>
            rows={campaigns}
            emptyText="Még nincs felvett kampány - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(c) => `/kampanyok/${c.id}`}
            deleteHref={canDelete ? (c) => `${ENTITY_PATHS.campaign}/${c.id}` : undefined}
            filterable
            columns={[
              {
                header: "Név",
                render: (c) =>
                  canEdit ? <EditableTableCell patchPath={`${ENTITY_PATHS.campaign}/${c.id}`} field="nev" value={c.nev} /> : c.nev,
                sortAccessor: (c) => c.nev,
              },
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
              {
                header: "Határidő",
                render: (c) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.campaign}/${c.id}`} field="hatarido" value={c.hatarido} type="date" />
                  ) : (
                    formatDate(c.hatarido)
                  ),
                sortAccessor: (c) => c.hatarido,
              },
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
