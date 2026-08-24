import { ENTITY_PATHS, formatDate, getCurrentUser, getFieldTypes, getMyPagePermissions, getTasks, Task } from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/feladatok";

export default async function FeladatokPage() {
  const [tasks, fieldTypes, currentUser, pagePermissions] = await Promise.all([
    getTasks(),
    getFieldTypes("task"),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const statusOptions = fieldTypes.allapot?.options ?? [];
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <Card title={`Feladatok (${tasks.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.task}
              addLabel="+ Új feladat hozzáadása"
              fields={[
                { name: "feladat", label: "Feladat", required: true },
                { name: "hatarido", label: "Határidő", type: "date" },
              ]}
            />
          )}
          <DataTable<Task>
            rows={tasks}
            emptyText="Még nincs felvett feladat - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(t) => `/feladatok/${t.id}`}
            deleteHref={canDelete ? (t) => `${ENTITY_PATHS.task}/${t.id}` : undefined}
            filterable
            columns={[
              {
                header: "Feladat",
                render: (t) =>
                  canEdit ? <EditableTableCell patchPath={`${ENTITY_PATHS.task}/${t.id}`} field="feladat" value={t.feladat} /> : t.feladat,
                sortAccessor: (t) => t.feladat,
              },
              {
                header: "Kategória",
                render: (t) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.task}/${t.id}`} field="kategoria" value={t.kategoria} />
                  ) : (
                    t.kategoria ?? "–"
                  ),
                sortAccessor: (t) => t.kategoria,
              },
              {
                header: "Határidő",
                render: (t) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.task}/${t.id}`} field="hatarido" value={t.hatarido} type="date" />
                  ) : (
                    formatDate(t.hatarido)
                  ),
                sortAccessor: (t) => t.hatarido,
              },
              {
                header: "Állapot",
                render: (t) => (
                  <EditableStatusBadge
                    patchPath={`${ENTITY_PATHS.task}/${t.id}`}
                    field="allapot"
                    value={t.allapot}
                    options={statusOptions}
                  />
                ),
                sortAccessor: (t) => t.allapot,
              },
              {
                header: "Kész",
                align: "right",
                render: (t) => <StatusBadge label={t.checked ? "Kész" : "Nyitott"} tone={t.checked ? "success" : "warning"} />,
                sortAccessor: (t) => (t.checked ? 1 : 0),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
