import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { Employee, ENTITY_PATHS, getCurrentUser, getEmployees, getMyPagePermissions } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/csapat";

/** Külsős: a közös crew-adatbázisból (lásd Vágók/Belsősök oldal) azok, akik
 * sem nem belsősök, sem nem vágók/kreatívok/stáb - vagyis a diszpó-küldés
 * után eseti (nem keretszerződéses) megbízási szerződést igénylő emberek. Ha
 * valakit belsősre/vágóra sorolunk át (tipus mező), automatikusan eltűnik
 * innen és megjelenik a másik nézetben - ugyanaz a tábla, csak szűrve. */
export default async function CsapatPage() {
  const [employees, currentUser, pagePermissions] = await Promise.all([getEmployees(), getCurrentUser(), getMyPagePermissions()]);
  const rows = employees.filter((e) => e.tipus === "kulsos");
  const canCreate = canDoAction(currentUser?.role, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser?.role, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser?.role, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Külsős (${rows.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.employee}
              addLabel="+ Új külsős hozzáadása"
              presetFields={{ tipus: "kulsos" }}
              fields={[
                { name: "full_name", label: "Név", required: true },
                { name: "email", label: "Email" },
              ]}
            />
          )}
          <DataTable<Employee>
            rows={rows}
            emptyText="Még nincs felvett külsős munkatárs."
            getHref={(e) => `/csapat/${e.id}`}
            deleteHref={canDelete ? (e) => `${ENTITY_PATHS.employee}/${e.id}` : undefined}
            filterable
            columns={[
              {
                header: "Név",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.employee}/${e.id}`} field="full_name" value={e.full_name} />
                  ) : (
                    e.full_name
                  ),
                sortAccessor: (e) => e.full_name,
              },
              {
                header: "Email",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.employee}/${e.id}`} field="email" value={e.email} />
                  ) : (
                    e.email ?? "–"
                  ),
                sortAccessor: (e) => e.email,
              },
              {
                header: "Telefon",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.employee}/${e.id}`} field="telefon" value={e.telefon} />
                  ) : (
                    e.telefon ?? "–"
                  ),
                sortAccessor: (e) => e.telefon,
              },
              {
                header: "Aktív",
                render: (e) => <StatusBadge label={e.is_active ? "Aktív" : "Inaktív"} tone={e.is_active ? "success" : "neutral"} />,
                sortAccessor: (e) => (e.is_active ? 1 : 0),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
