import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailGrid } from "@/components/DetailGrid";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getRecord, getRecordsByIds, getRelated } from "@/lib/api";
import { toDetailFields } from "@/lib/detail";

export default async function EquipmentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const equipmentId = Number(id);
  const equipment = await getRecord(ENTITY_PATHS.equipment, equipmentId);
  if (!equipment) notFound();

  const projectIds = Array.isArray(equipment.project_ids) ? (equipment.project_ids as number[]) : [];

  const [assignments, projects] = await Promise.all([
    getRelated("/api/v1/assignments", { equipment_id: equipmentId }),
    getRecordsByIds(ENTITY_PATHS.project, projectIds),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/felszereles" label="Felszerelés" />

        <Card title={String(equipment.nev ?? `Eszköz #${equipment.id}`)}>
          <DetailGrid fields={toDetailFields(equipment, ["project_ids"])} />
        </Card>

        <Card title={`Projektek (${projects.length})`}>
          <RelatedTable
            rows={projects}
            emptyText="Ez az eszköz még egyetlen projekthez sincs hozzárendelve."
            getHref={(p) => `/projektek/${p.id}`}
          />
        </Card>

        <Card title={`Kivitelek (${assignments.length})`}>
          <RelatedTable rows={assignments} emptyText="Nincs eszközkivitel rögzítve ehhez az eszközhöz." />
        </Card>
      </div>
    </div>
  );
}
