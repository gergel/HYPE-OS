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
                // A kód alatt ott a projekt NEVE is: a puszta kódról ránézésre
                // senki nem tudja, melyik munkáról van szó.
                header: "Projektkód",
                render: (pc) => (
                  <span>
                    {canEdit ? (
                      <EditableTableCell patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`} field="projektkod" value={pc.projektkod} />
                    ) : (
                      pc.projektkod
                    )}
                    {pc.project_nev && (
                      <span className="mt-0.5 block text-[11.5px] text-text-muted">{pc.project_nev}</span>
                    )}
                  </span>
                ),
                sortAccessor: (pc) => pc.projektkod,
              },
              {
                header: "Ügyfél",
                render: (pc) => clientNameById.get(pc.client_id) ?? "–",
                sortAccessor: (pc) => clientNameById.get(pc.client_id),
              },
              {
                header: "Helyszín",
                render: (pc) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`} field="helyszin" value={pc.helyszin} />
                  ) : (
                    (pc.helyszin ?? "–")
                  ),
                sortAccessor: (pc) => pc.helyszin,
              },
              {
                // A dátum alatt a hozzá tartozó megjegyzés ("2 nap", "csúszik")
                // - ez a mező eddig sehol nem látszott a listán.
                header: "Dátum",
                render: (pc) => (
                  <span>
                    {canEdit ? (
                      <EditableTableCell patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`} field="datum" value={pc.datum} type="date" />
                    ) : (
                      formatDate(pc.datum)
                    )}
                    {pc.datum_megjegyzes && (
                      <span className="mt-0.5 block text-[11.5px] text-text-muted">{pc.datum_megjegyzes}</span>
                    )}
                  </span>
                ),
                sortAccessor: (pc) => pc.datum,
              },
              {
                header: "Bevétel",
                align: "right",
                render: (pc) => formatHuf(pc.bevetel),
                sortAccessor: (pc) => pc.bevetel,
              },
              {
                // Kiadás = minden projektkiadás + az utómunka költsége, ugyanaz,
                // amit az adatlap "Összes költség (kiadások + utómunka)" néven
                // mutat (lásd models/project_code.osszes_koltseg).
                header: "Kiadás",
                align: "right",
                render: (pc) => formatHuf(pc.osszes_koltseg),
                sortAccessor: (pc) => pc.osszes_koltseg,
              },
              {
                header: "Profit",
                align: "right",
                render: (pc) => (
                  <span className={pc.becsult_profit < 0 ? "text-text-danger" : undefined}>
                    {formatHuf(pc.becsult_profit)}
                  </span>
                ),
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
