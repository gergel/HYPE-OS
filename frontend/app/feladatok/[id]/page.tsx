import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailGrid } from "@/components/DetailGrid";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getRecord } from "@/lib/api";
import { toDetailFields } from "@/lib/detail";

export default async function TaskDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const taskId = Number(id);
  const task = await getRecord(ENTITY_PATHS.task, taskId);
  if (!task) notFound();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/feladatok" label="Feladatok" />

        <Card title={String(task.feladat ?? `Feladat #${task.id}`)}>
          <DetailGrid fields={toDetailFields(task)} />
        </Card>
      </div>
    </div>
  );
}
