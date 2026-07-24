import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, Equipment, getCurrentUser, getEquipment, getFieldTypes, getMyPagePermissions } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/felszereles";

export default async function FelszerelesPage() {
  const [equipment, fieldTypes, currentUser, pagePermissions] = await Promise.all([
    getEquipment(),
    getFieldTypes("equipment"),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const statusOptions = fieldTypes.allapot?.options ?? [];
  const canCreate = canDoAction(currentUser?.role, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser?.role, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser?.role, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Felszerelés (${equipment.length})`}>
          <div className="mb-3 flex justify-end">
            <a
              href="/felszereles/leltarazas"
              className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
            >
              Leltározás
            </a>
          </div>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.equipment}
              addLabel="+ Új eszköz hozzáadása"
              fields={[
                { name: "nev", label: "Név", required: true },
                { name: "kategoria", label: "Kategória" },
              ]}
            />
          )}
          <DataTable<Equipment>
            rows={equipment}
            emptyText="Még nincs felvett eszköz - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(e) => `/felszereles/${e.id}`}
            deleteHref={canDelete ? (e) => `${ENTITY_PATHS.equipment}/${e.id}` : undefined}
            filterable
            columns={[
              {
                header: "Név",
                render: (e) =>
                  canEdit ? <EditableTableCell patchPath={`${ENTITY_PATHS.equipment}/${e.id}`} field="nev" value={e.nev} /> : e.nev,
                sortAccessor: (e) => e.nev,
              },
              { header: "Kategória", render: (e) => e.kategoria ?? "–", sortAccessor: (e) => e.kategoria },
              {
                header: "Állapot",
                render: (e) => (
                  <EditableStatusBadge
                    patchPath={`${ENTITY_PATHS.equipment}/${e.id}`}
                    field="allapot"
                    value={e.allapot}
                    options={statusOptions}
                  />
                ),
                sortAccessor: (e) => e.allapot,
              },
              {
                header: "Track mode",
                render: (e) => <StatusBadge label={e.track_mode === "stock" ? "Készlet" : "Egyedi"} tone="neutral" />,
                sortAccessor: (e) => e.track_mode,
              },
              {
                header: "Mennyiség",
                align: "right",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell
                      patchPath={`${ENTITY_PATHS.equipment}/${e.id}`}
                      field="osszes_mennyiseg"
                      value={e.osszes_mennyiseg}
                      type="number"
                    />
                  ) : (
                    e.osszes_mennyiseg ?? "–"
                  ),
                sortAccessor: (e) => e.osszes_mennyiseg,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
