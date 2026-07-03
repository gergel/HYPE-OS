import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailGrid } from "@/components/DetailGrid";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getRecord } from "@/lib/api";
import { toDetailFields } from "@/lib/detail";

export default async function RevenueDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const revenueId = Number(id);
  const revenue = await getRecord(ENTITY_PATHS.revenue, revenueId);
  if (!revenue) notFound();

  const projectCode = revenue.project_code_id ? await getRecord(ENTITY_PATHS.projectCode, Number(revenue.project_code_id)) : null;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/penzugyek" label="Pénzügyek" />

        <Card title={String(revenue.bevetel_formaja ?? `Bevétel #${revenue.id}`)}>
          <div className="mb-4 flex flex-wrap gap-4 text-[13px] text-text-secondary">
            {projectCode && (
              <a href={`/projektek/project-kodok/${projectCode.id}`} className="text-text-accent hover:underline">
                Project Code: {String(projectCode.projektkod)}
              </a>
            )}
          </div>
          <DetailGrid fields={toDetailFields(revenue, ["project_code_id"])} />
        </Card>
      </div>
    </div>
  );
}
