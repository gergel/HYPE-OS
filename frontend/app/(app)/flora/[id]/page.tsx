import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailSections } from "@/components/DetailSections";
import { FloraCommentsSection } from "@/components/flora/FloraCommentsSection";
import { ReadOnlyDetailField } from "@/components/ReadOnlyDetailField";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getDetailTabs,
  getEmployees,
  getFieldTypes,
  getFloraKommentek,
  getMyPagePermissions,
  getRecord,
  getVisibleFields,
} from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";

const PAGE = "/flora";
//: Egyszemélyes idegenkulcs-mezők - nyers szám helyett névre feloldva
//: jelennek meg (lásd components/ReadOnlyDetailField.tsx).
const SZEMELY_MEZOK: { key: "felelos_id" | "felvezette_id"; label: string }[] = [
  { key: "felelos_id", label: "Felelős" },
  { key: "felvezette_id", label: "Felvezette" },
];

export default async function FloraDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const feladatId = Number(id);
  const [feladat, visibleFields, fieldTypes, dbTabs, pagePermissions, employees, kommentek] = await Promise.all([
    getRecord(ENTITY_PATHS.floraFeladat, feladatId),
    getVisibleFields("floraFeladat"),
    getFieldTypes("floraFeladat"),
    getDetailTabs("floraFeladat"),
    getMyPagePermissions(),
    getEmployees(),
    getFloraKommentek(feladatId),
  ]);
  if (!feladat) notFound();

  const patchPath = `${ENTITY_PATHS.floraFeladat}/${feladat.id}`;
  const employeeName = new Map(employees.map((e) => [e.id, e.full_name]));

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath,
    record: feladat,
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
    alwaysHidden: SZEMELY_MEZOK.map((m) => m.key),
    widgets: Object.fromEntries(
      SZEMELY_MEZOK.map(({ key, label }) => {
        const empId = feladat[key] as number | null;
        return [key, <ReadOnlyDetailField key={key} label={label} value={empId ? (employeeName.get(empId) ?? `#${empId}`) : null} />];
      }),
    ),
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <div className="space-y-2">
          <BackLink href="/flora" label="FLÓRA" />
          <h1 className="t-page">{String(feladat.megnevezes ?? `Tétel #${feladat.id}`)}</h1>
        </div>

        <DetailSections sections={tabs} />

        {/* Hozzászólások - a Notion-import a kártya Notion-beli kommentjeit
            is ide hozza, tehát a régi beszélgetések sem vesznek el (lásd
            backend notion_import/importers_wave4.import_flora_design). */}
        <Card title="Hozzászólások">
          <FloraCommentsSection
            floraId={feladatId}
            initialComments={kommentek}
            mentionableEmployees={employees.map((e) => ({ id: e.id, full_name: e.full_name }))}
          />
        </Card>
      </div>
    </div>
  );
}
