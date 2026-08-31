import Link from "next/link";
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
  // A kategória LEGÖRDÜLŐ (a felhasználó kérése): a már használt kategóriák
  // közül lehet választani - felvitelkor újat is be lehet gépelni, a
  // táblázatban pedig a meglévők közül vált.
  const kategoriak = Array.from(
    new Set(equipment.map((e) => e.kategoria).filter((k): k is string => !!k && !!k.trim())),
  ).sort((a, b) => a.localeCompare(b, "hu"));
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <Card title={`Felszerelés (${equipment.length})`}>
          {/* A leltározás a leltár SZERKESZTÉSE (tételek megjelölése, session
              indítása) - aki csak nézheti az eszközöket (pl. a diszpós, aki a
              projekten technikát vezet fel), annak a gomb csak 403-at adna. */}
          {canEdit && (
            <div className="mb-3 flex justify-end">
              <Link
                href="/felszereles/leltarazas"
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
              >
                Leltározás
              </Link>
            </div>
          )}
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.equipment}
              addLabel="+ Új eszköz hozzáadása"
              fields={[
                { name: "nev", label: "Név", required: true },
                // Legördülő javaslatok a meglévő kategóriákból - de új
                // kategória is beírható (különben sosem születhetne új).
                { name: "kategoria", label: "Kategória", suggestions: kategoriak },
              ]}
            />
          )}
          <DataTable<Equipment>
            rows={equipment}
            emptyText="Még nincs felvett eszköz - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(e) => `/felszereles/${e.id}`}
            // FELUGRÓ ablakban nyílik az eszköz adatlapja (a felhasználó
            // kérése): ott látszik, melyik forgatásokon volt és összesen
            // hányon - visszalépéskor a lista szűrése/görgetése megmarad.
            openInModal
            deleteHref={canDelete ? (e) => `${ENTITY_PATHS.equipment}/${e.id}` : undefined}
            filterable
            columns={[
              {
                header: "Név",
                render: (e) =>
                  canEdit ? <EditableTableCell patchPath={`${ENTITY_PATHS.equipment}/${e.id}`} field="nev" value={e.nev} /> : e.nev,
                sortAccessor: (e) => e.nev,
              },
              {
                header: "Kategória",
                render: (e) =>
                  canEdit ? (
                    <EditableStatusBadge
                      patchPath={`${ENTITY_PATHS.equipment}/${e.id}`}
                      field="kategoria"
                      value={e.kategoria}
                      options={kategoriak}
                      placeholder="Nincs kategória"
                    />
                  ) : (
                    (e.kategoria ?? "–")
                  ),
                sortAccessor: (e) => e.kategoria,
              },
              {
                header: "Állapot",
                render: (e) =>
                  canEdit ? (
                    <EditableStatusBadge
                      patchPath={`${ENTITY_PATHS.equipment}/${e.id}`}
                      field="allapot"
                      value={e.allapot}
                      options={statusOptions}
                    />
                  ) : (
                    <StatusBadge label={e.allapot ?? "–"} tone="neutral" />
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
