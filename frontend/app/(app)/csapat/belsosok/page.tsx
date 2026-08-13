import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StopClickPropagation } from "@/components/StopClickPropagation";
import { TopBar } from "@/components/TopBar";
import { BelsosAddWidget } from "@/components/BelsosAddWidget";
import { EmployeeActiveToggle } from "@/components/VagoInlineFields";
import { ENTITY_PATHS, formatHuf, getCurrentUser, getEmployees, getMyPagePermissions } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/csapat";

/** Belsősök: a crew-adatbázisból (külsős + belsős) azok, akiket az admin
 * belsősként jelölt meg (Employee.tipus == "belsos") - bármikor bővíthető a
 * teljes crew listából, ugyanúgy ahogy a Vágók oldal a tipus=="vago" szűrést
 * használja, csak itt van egy "hozzáadás" widget is, mert idesorolás admin
 * döntés, nem egy fix Notion-import-béli kategória. */
export default async function BelsosokPage() {
  const [employees, currentUser, pagePermissions] = await Promise.all([getEmployees(), getCurrentUser(), getMyPagePermissions()]);
  const rows = employees.filter((e) => e.tipus === "belsos");
  const candidates = employees.filter((e) => e.tipus !== "belsos");
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Belsősök (${rows.length})`}>
          {canCreate && <BelsosAddWidget candidates={candidates} />}
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.employee}
              addLabel="+ Új belsős hozzáadása"
              presetFields={{ tipus: "belsos" }}
              fields={[
                { name: "full_name", label: "Név", required: true },
                { name: "email", label: "Email" },
              ]}
            />
          )}
          <DataTable<(typeof rows)[number]>
            filterable
            rows={rows}
            emptyText="Még nincs belsősként megjelölt munkatárs - válassz valakit fent a crew listából."
            getHref={(e) => `/csapat/${e.id}?from=belsosok`}
            deleteHref={canDelete ? (e) => `${ENTITY_PATHS.employee}/${e.id}` : undefined}
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
                // Mennyibe kerül egy munkanapja: ebből számoljuk, mennyi saját
                // munka van egy projektben (lásd backend
                // services/belsos_koltseg.py). Kiadás-sor NEM lesz belőle - a
                // havi bér a hónap végén megy be egyben.
                header: "Napidíj",
                align: "right",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell
                      patchPath={`${ENTITY_PATHS.employee}/${e.id}`}
                      field="napi_dij"
                      value={e.napi_dij}
                      type="number"
                      placeholder="Nincs megadva"
                    />
                  ) : (
                    (e.napi_dij != null ? formatHuf(e.napi_dij) : "–")
                  ),
                sortAccessor: (e) => e.napi_dij,
              },
              {
                header: "Aktív",
                render: (e) => (
                  <StopClickPropagation>
                    <EmployeeActiveToggle employeeId={e.id} initialActive={e.is_active} />
                  </StopClickPropagation>
                ),
                sortAccessor: (e) => (e.is_active ? 1 : 0),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
