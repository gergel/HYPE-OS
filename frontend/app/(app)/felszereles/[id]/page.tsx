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
  const equipment = await getRecord(ENTITY_PATHS.equipment, equipmentId);
  if (!equipment) notFound();

  const projectIds = Array.isArray(equipment.project_ids) ? (equipment.project_ids as number[]) : [];

  const [assignments, projects, visibleFields, fieldTypes, dbTabs, pagePermissions] = await Promise.all([
    getRelated("/api/v1/assignments", { equipment_id: equipmentId }),
    getRecordsByIds(ENTITY_PATHS.project, projectIds),
    getVisibleFields("equipment"),
    getFieldTypes("equipment"),
    getDetailTabs("equipment"),
    getMyPagePermissions(),
  ]);

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
      <div className="flex-1 space-y-8 p-8">
        <div className="space-y-2">
          <BackLink href="/felszereles" label="Felszerelés" />
          <h1 className="t-page">{String(equipment.nev ?? `Eszköz #${equipment.id}`)}</h1>
        </div>

        <DetailSections sections={tabs} />

        <Card title={`Projektek (${projects.length})`}>
          <RelatedTable
            rows={projects}
            emptyText="Ez az eszköz még egyetlen projekthez sincs hozzárendelve."
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
