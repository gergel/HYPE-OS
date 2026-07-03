import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailGrid } from "@/components/DetailGrid";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getRecord, getRelated } from "@/lib/api";
import { toDetailFields } from "@/lib/detail";

export default async function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectId = Number(id);
  const project = await getRecord(ENTITY_PATHS.project, projectId);
  if (!project) notFound();

  const [projectCode, campaign, deliverables] = await Promise.all([
    project.project_code_id ? getRecord(ENTITY_PATHS.projectCode, Number(project.project_code_id)) : null,
    project.campaign_id ? getRecord(ENTITY_PATHS.campaign, Number(project.campaign_id)) : null,
    getRelated(ENTITY_PATHS.deliverable, { project_id: projectId }),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/projektek" label="Projektek" />

        <Card title={String(project.nev ?? `Projekt #${project.id}`)}>
          <div className="mb-4 flex flex-wrap gap-4 text-[13px] text-text-secondary">
            {projectCode && (
              <a href={`/projektek/project-kodok/${projectCode.id}`} className="text-text-accent hover:underline">
                Project Code: {String(projectCode.projektkod)}
              </a>
            )}
            {campaign && (
              <a href={`/kampanyok/${campaign.id}`} className="text-text-accent hover:underline">
                Kampány: {String(campaign.nev)}
              </a>
            )}
          </div>
          <DetailGrid fields={toDetailFields(project, ["project_code_id", "campaign_id"])} />
        </Card>

        <Card title={`Utómunka (${deliverables.length})`}>
          <RelatedTable rows={deliverables} emptyText="Nincs vágandó anyag ehhez a projekthez." getHref={(d) => `/utomunka/${d.id}`} />
        </Card>
      </div>
    </div>
  );
}
