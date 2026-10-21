import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { DetailSections } from "@/components/DetailSections";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getDetailTabs, getFieldTypes, getMyPagePermissions, getRecord, getVisibleFields } from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";

const PAGE = "/agi";

export default async function AgiTodoDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const itemId = Number(id);
  const [item, visibleFields, fieldTypes, dbTabs, pagePermissions] = await Promise.all([
    getRecord(ENTITY_PATHS.agiTodo, itemId),
    getVisibleFields("agiTodo"),
    getFieldTypes("agiTodo"),
    getDetailTabs("agiTodo"),
    getMyPagePermissions(),
  ]);
  if (!item) notFound();

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath: `${ENTITY_PATHS.agiTodo}/${item.id}`,
    record: item,
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
          <BackLink href="/agi" label="ÁGI" />
          <h1 className="t-page">{String(item.feladat ?? `Feladat #${item.id}`)}</h1>
        </div>

        <DetailSections sections={tabs} />
      </div>
    </div>
  );
}
