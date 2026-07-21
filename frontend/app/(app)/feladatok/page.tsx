import { ENTITY_PATHS, formatDate, getFieldTypes, getTasks, Task } from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";

export default async function FeladatokPage() {
  const [tasks, fieldTypes] = await Promise.all([getTasks(), getFieldTypes("task")]);
  const statusOptions = fieldTypes.allapot?.options ?? [];

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Feladatok (${tasks.length})`}>
          <DataTable<Task>
            rows={tasks}
            emptyText="Még nincs felvett feladat - importáld a Notionból, vagy adj hozzá egyet a /api/v1/tasks végponton."
            getHref={(t) => `/feladatok/${t.id}`}
            deleteHref={(t) => `${ENTITY_PATHS.task}/${t.id}`}
            filterable
            columns={[
              { header: "Feladat", render: (t) => t.feladat, sortAccessor: (t) => t.feladat },
              { header: "Kategória", render: (t) => t.kategoria ?? "–", sortAccessor: (t) => t.kategoria },
              { header: "Határidő", render: (t) => formatDate(t.hatarido), sortAccessor: (t) => t.hatarido },
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
