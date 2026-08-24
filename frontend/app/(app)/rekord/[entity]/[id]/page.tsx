import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { DetailSections } from "@/components/DetailSections";
import { TopBar } from "@/components/TopBar";
import { getDetailTabs, getFieldTypes, getMyPagePermissions, getRecord, getVisibleFields } from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";
import { recordEntity } from "@/lib/recordEntities";

/** Generikus adatlap azoknak az entitásoknak, amiknek nincs saját oldaluk
 * (díj, munkaidő-elszámolás, visszajelzés, eszközfoglalás, kapcsolattartó) -
 * lásd lib/recordEntities.ts. Ugyanaz a szerkeszthető mező-rács, mint a
 * "rendes" adatlapokon: aki az adott oldalon szerkeszthet, itt is minden
 * mezőt tud írni.
 *
 * Ezek a rekordok eddig csak kapcsolódó táblákban, kattinthatatlan sorként
 * jelentek meg, tehát sehol nem lehetett őket módosítani (pl. egy elrontott
 * utómunka-idő). */
export default async function GenericRecordPage({
  params,
}: {
  params: Promise<{ entity: string; id: string }>;
}) {
  const { entity, id } = await params;
  const config = recordEntity(entity);
  if (!config) notFound();

  const record = await getRecord(config.path, Number(id));
  if (!record) notFound();

  const [visibleFields, fieldTypes, dbTabs, pagePermissions] = await Promise.all([
    getVisibleFields(config.entityType),
    getFieldTypes(config.entityType),
    getDetailTabs(config.entityType),
    getMyPagePermissions(),
  ]);

  const sections = buildFieldTabs({
    page: config.page,
    patchPath: `${config.path}/${record.id}`,
    record,
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <div className="space-y-2">
          <BackLink href={config.page} label="Vissza" />
          <h1 className="t-page">
          {config.label} #{String(record.id)}
          </h1>
        </div>
        <DetailSections sections={sections} />
      </div>
    </div>
  );
}
