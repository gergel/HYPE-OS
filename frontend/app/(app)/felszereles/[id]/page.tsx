import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getFieldTypes, getRecord, getRecordsByIds, getRelated, getVisibleFields } from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";

export default async function EquipmentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const equipmentId = Number(id);
  const equipment = await getRecord(ENTITY_PATHS.equipment, equipmentId);
  if (!equipment) notFound();

  const projectIds = Array.isArray(equipment.project_ids) ? (equipment.project_ids as number[]) : [];

  const [assignments, projects, visibleFields, fieldTypes] = await Promise.all([
    getRelated("/api/v1/assignments", { equipment_id: equipmentId }),
    getRecordsByIds(ENTITY_PATHS.project, projectIds),
    getVisibleFields("equipment"),
    getFieldTypes("equipment"),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/felszereles" label="Felszerelés" />

        <Card title={String(equipment.nev ?? `Eszköz #${equipment.id}`)}>
          <EditableDetailGrid
            patchPath={`${ENTITY_PATHS.equipment}/${equipment.id}`}
            fields={toEditableDetailFields(
              { ...equipment, forgatasok_szama: projectIds.length },
              ["project_ids"],
              visibleFields,
              fieldTypes,
            )}
          />
        </Card>

        <Card title={`Projektek (${projects.length})`}>
          <RelatedTable
            rows={projects}
            emptyText="Ez az eszköz még egyetlen projekthez sincs hozzárendelve."
            getHref={(p) => `/projektek/${p.id}`}
          />
        </Card>

        <Card title={`Foglalások (${assignments.length})`}>
          <RelatedTable rows={assignments} emptyText="Nincs foglalás rögzítve ehhez az eszközhöz." deleteBasePath={ENTITY_PATHS.assignment} />
        </Card>
      </div>
    </div>
  );
}
