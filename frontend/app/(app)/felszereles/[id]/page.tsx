import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailSections } from "@/components/DetailSections";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getDetailTabs, getFieldTypes, getMyPagePermissions, getRecord, getRecordsByIds, getRelated, getVisibleFields } from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";

const PAGE = "/felszereles";

export default async function EquipmentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const equipmentId = Number(id);

  // A "projects" lista az EGYETLEN, ami az equipment rekordtól függ (a
  // project_ids mezőjétől) - a többi csak equipmentId-t vagy semmit nem kér,
  // ezért azok a getRecord-dal EGYSZERRE indulnak, nem utána: egy kevesebb
  // kör az oldalbetöltésnél.
  const [equipment, assignments, visibleFields, fieldTypes, dbTabs, pagePermissions] = await Promise.all([
    getRecord(ENTITY_PATHS.equipment, equipmentId),
    getRelated("/api/v1/assignments", { equipment_id: equipmentId }),
    getVisibleFields("equipment"),
    getFieldTypes("equipment"),
    getDetailTabs("equipment"),
    getMyPagePermissions(),
  ]);
  if (!equipment) notFound();

  const projectIds = Array.isArray(equipment.project_ids) ? (equipment.project_ids as number[]) : [];
  const projects = await getRecordsByIds(ENTITY_PATHS.project, projectIds);

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath: `${ENTITY_PATHS.equipment}/${equipment.id}`,
    // A ténylegesen betöltött projektek számát mutatjuk, nem a nyers
    // project_ids hosszát - így a szám sosem térhet el attól, amit a
    // "Projektek" szekció alant ténylegesen felsorol (pl. ha egy hivatkozott
    // projekt rekord lekérése valamiért nem sikerülne).
    record: { ...equipment, forgatasok_szama: projects.length },
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
    alwaysHidden: ["project_ids"],
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <div className="space-y-2">
          <BackLink href="/felszereles" label="Felszerelés" />
          <h1 className="t-page">{String(equipment.nev ?? `Eszköz #${equipment.id}`)}</h1>
        </div>

        <DetailSections sections={tabs} />

        <Card title={`Forgatások (összesen ${projects.length})`}>
          <RelatedTable
            rows={projects}
            emptyText="Ez az eszköz még egyetlen forgatáson sem volt."
            getHref={(p) => `/projektek/${p.id}`}
          />
        </Card>

        <Card title={`Foglalások (${assignments.length})`}>
          <RelatedTable
            rows={assignments}
            emptyText="Nincs foglalás rögzítve ehhez az eszközhöz."
            entityKey="assignment"
            deleteBasePath={ENTITY_PATHS.assignment}
          />
        </Card>
      </div>
    </div>
  );
}
