import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  formatDate,
  formatHuf,
  getClients,
  getCurrentUser,
  getFieldTypes,
  getMyPagePermissions,
  getProjectCodes,
  ProjectCode,
} from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/projektek/project-kodok";

export default async function ProjectKodokPage() {
  const [projectCodes, clients, fieldTypes, currentUser, pagePermissions] = await Promise.all([
    getProjectCodes(),
    getClients(),
    getFieldTypes("projectCode"),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const clientNameById = new Map(clients.map((c) => [c.id, c.nev]));
  const statusOptions = fieldTypes.esemeny_allapota?.options ?? [];
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Project Code-ok (${projectCodes.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.projectCode}
              addLabel="+ Új Project Code hozzáadása"
              fields={[
                { name: "projektkod", label: "Projektkód", required: true },
                { name: "client_id", label: "Ügyfél", type: "select", required: true, options: clients.map((c) => ({ value: c.id, label: c.nev })) },
                { name: "datum", label: "Dátum", type: "date" },
              ]}
            />
          )}
          <DataTable<ProjectCode>
            rows={projectCodes}
            emptyText="Még nincs felvett Project Code - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(pc) => `/projektek/project-kodok/${pc.id}`}
            deleteHref={canDelete ? (pc) => `${ENTITY_PATHS.projectCode}/${pc.id}` : undefined}
            filterable
            columns={[
              {
                header: "Projektkód",
                render: (pc) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`} field="projektkod" value={pc.projektkod} />
                  ) : (
                    pc.projektkod
                  ),
                sortAccessor: (pc) => pc.projektkod,
              },
              {
                header: "Ügyfél",
                render: (pc) => clientNameById.get(pc.client_id) ?? "–",
                sortAccessor: (pc) => clientNameById.get(pc.client_id),
              },
              {
                header: "Dátum",
                render: (pc) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`} field="datum" value={pc.datum} type="date" />
                  ) : (
                    formatDate(pc.datum)
                  ),
                sortAccessor: (pc) => pc.datum,
              },
              {
                header: "Összes költség",
                align: "right",
                render: (pc) => formatHuf(pc.osszes_koltseg),
                sortAccessor: (pc) => pc.osszes_koltseg,
              },
              {
                header: "Becsült profit",
                align: "right",
                render: (pc) => formatHuf(pc.becsult_profit),
                sortAccessor: (pc) => pc.becsult_profit,
              },
              {
                header: "Státusz",
                align: "right",
                render: (pc) => (
                  <EditableStatusBadge
                    patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`}
                    field="esemeny_allapota"
                    value={pc.esemeny_allapota}
                    options={statusOptions}
                  />
                ),
                sortAccessor: (pc) => pc.esemeny_allapota,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
