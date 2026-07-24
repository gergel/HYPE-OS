import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { TopBar } from "@/components/TopBar";
import { Client, ENTITY_PATHS, getClients, getCurrentUser, getMyPagePermissions } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/ugyfelek";

export default async function UgyfelekPage() {
  const [clients, currentUser, pagePermissions] = await Promise.all([getClients(), getCurrentUser(), getMyPagePermissions()]);
  const canCreate = canDoAction(currentUser?.role, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser?.role, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser?.role, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Ügyfelek (${clients.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.client}
              addLabel="+ Új ügyfél hozzáadása"
              fields={[
                { name: "nev", label: "Név", required: true },
                { name: "adoszam", label: "Adószám" },
                { name: "szekhely", label: "Székhely" },
              ]}
            />
          )}
          <DataTable<Client>
            rows={clients}
            emptyText="Még nincs felvett ügyfél - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(c) => `/ugyfelek/${c.id}`}
            deleteHref={canDelete ? (c) => `${ENTITY_PATHS.client}/${c.id}` : undefined}
            filterable
            columns={[
              {
                header: "Név",
                render: (c) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.client}/${c.id}`} field="nev" value={c.nev} />
                  ) : (
                    c.nev
                  ),
                sortAccessor: (c) => c.nev,
              },
              {
                header: "Adószám",
                render: (c) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.client}/${c.id}`} field="adoszam" value={c.adoszam} />
                  ) : (
                    c.adoszam ?? "–"
                  ),
                sortAccessor: (c) => c.adoszam,
              },
              {
                header: "Székhely",
                render: (c) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.client}/${c.id}`} field="szekhely" value={c.szekhely} />
                  ) : (
                    c.szekhely ?? "–"
                  ),
                sortAccessor: (c) => c.szekhely,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
