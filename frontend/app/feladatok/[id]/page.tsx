import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getFieldTypes, getRecord, getVisibleFields } from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";

export default async function TaskDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const taskId = Number(id);
  const [task, visibleFields, fieldTypes] = await Promise.all([
    getRecord(ENTITY_PATHS.task, taskId),
    getVisibleFields("task"),
    getFieldTypes("task"),
  ]);
  if (!task) notFound();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/feladatok" label="Feladatok" />

        <Card title={String(task.feladat ?? `Feladat #${task.id}`)}>
          <EditableDetailGrid
            patchPath={`${ENTITY_PATHS.task}/${task.id}`}
            fields={toEditableDetailFields(task, [], visibleFields, fieldTypes)}
          />
        </Card>
      </div>
    </div>
  );
}
