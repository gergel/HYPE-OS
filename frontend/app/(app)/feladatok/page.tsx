import Link from "next/link";
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

export default async function FeladatokPage({
  searchParams,
}: {
  searchParams: Promise<{ szures?: string }>;
}) {
  const [{ szures }, osszesFeladat, fieldTypes, currentUser, pagePermissions] = await Promise.all([
    searchParams,
    getTasks(),
    getFieldTypes("task"),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const statusOptions = fieldTypes.allapot?.options ?? [];

  // ?szures=lejart: a dashboard "lejárt feladat határidő" figyelmeztetése
  // ezzel nyitja az oldalt - ugyanaz a definíció, mint a számlálóban (lásd
  // backend routes/dashboard.py): a határidő a múltban van, és a feladat
  // nincs készre pipálva.
  const csakLejart = szures === "lejart";
  const ma = new Date();
  const maNap = `${ma.getFullYear()}-${String(ma.getMonth() + 1).padStart(2, "0")}-${String(ma.getDate()).padStart(2, "0")}`;
  const tasks = csakLejart
    ? osszesFeladat.filter(
        (t) =>
          t.hatarido !== null &&
          t.hatarido.slice(0, 10) < maNap &&
          !t.checked &&
          // Az ARCHIVÁLT feladat nem lejárt teendő (a felhasználó kérése) -
          // ugyanaz a kivétel, mint a dashboard számlálójában (lásd backend
          // routes/dashboard.py lejart_feladat).
          (t.allapot ?? "").toLowerCase() !== "archived",
      )
    : osszesFeladat;
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        {csakLejart && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] bg-bg-warning px-3 py-2.5 text-[13px] text-text-warning">
            <span>
              Csak a lejárt határidejű feladatok látszanak ({tasks.length}) - amiknek a határideje
              elmúlt, de nincsenek készre pipálva.
            </span>
            <Link
              href="/feladatok"
              className="rounded-[var(--radius)] border border-text-warning/40 px-2.5 py-1 font-medium hover:opacity-80"
            >
              Szűrés kikapcsolása
            </Link>
          </div>
        )}
        <Card title={csakLejart ? `Lejárt feladatok (${tasks.length})` : `Feladatok (${tasks.length})`}>
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
