import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { DetailSections } from "@/components/DetailSections";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getDetailTabs, getFieldTypes, getMyPagePermissions, getRecord, getVisibleFields } from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";

const PAGE = "/feladatok";

export default async function TaskDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const taskId = Number(id);
  const [task, visibleFields, fieldTypes, dbTabs, pagePermissions] = await Promise.all([
    getRecord(ENTITY_PATHS.task, taskId),
    getVisibleFields("task"),
    getFieldTypes("task"),
    getDetailTabs("task"),
    getMyPagePermissions(),
  ]);
  if (!task) notFound();

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath: `${ENTITY_PATHS.task}/${task.id}`,
    record: task,
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
          <BackLink href="/feladatok" label="Feladatok" />
          <h1 className="t-page">{String(task.feladat ?? `Feladat #${task.id}`)}</h1>
        </div>

        <DetailSections sections={tabs} />
      </div>
    </div>
  );
}
