import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailGrid } from "@/components/DetailGrid";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getRecord, getRelated } from "@/lib/api";
import { toDetailFields } from "@/lib/detail";

export default async function DeliverableDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const deliverableId = Number(id);
  const deliverable = await getRecord(ENTITY_PATHS.deliverable, deliverableId);
  if (!deliverable) notFound();

  const [projectCode, project, vago, campaign, timesheets, feedbacks] = await Promise.all([
    deliverable.project_code_id ? getRecord(ENTITY_PATHS.projectCode, Number(deliverable.project_code_id)) : null,
    deliverable.project_id ? getRecord(ENTITY_PATHS.project, Number(deliverable.project_id)) : null,
    deliverable.vago_employee_id ? getRecord(ENTITY_PATHS.employee, Number(deliverable.vago_employee_id)) : null,
    deliverable.campaign_id ? getRecord(ENTITY_PATHS.campaign, Number(deliverable.campaign_id)) : null,
    getRelated(ENTITY_PATHS.timesheet, { deliverable_id: deliverableId }),
    getRelated(ENTITY_PATHS.feedback, { deliverable_id: deliverableId }),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/utomunka" label="Utómunka" />

        <Card title={String(deliverable.projekt_neve ?? `Anyag #${deliverable.id}`)}>
          <div className="mb-4 flex flex-wrap gap-4 text-[13px] text-text-secondary">
            {projectCode && (
              <a href={`/projektek/project-kodok/${projectCode.id}`} className="text-text-accent hover:underline">
                Project Code: {String(projectCode.projektkod)}
              </a>
            )}
            {project && (
              <a href={`/projektek/${project.id}`} className="text-text-accent hover:underline">
                Projekt: {String(project.nev)}
              </a>
            )}
            {vago && (
              <a href={`/csapat/${vago.id}`} className="text-text-accent hover:underline">
                Vágó: {String(vago.full_name)}
              </a>
            )}
            {campaign && (
              <a href={`/kampanyok/${campaign.id}`} className="text-text-accent hover:underline">
                Kampány: {String(campaign.nev)}
              </a>
            )}
          </div>
          <DetailGrid
            fields={toDetailFields(deliverable, ["project_code_id", "project_id", "vago_employee_id", "campaign_id"])}
          />
        </Card>

        <Card title={`Munkaidő-elszámolások (${timesheets.length})`}>
          <RelatedTable
            rows={timesheets}
            emptyText="Nincs munkaidő-elszámolás ehhez az anyaghoz."
            deleteBasePath={ENTITY_PATHS.timesheet}
          />
        </Card>

        <Card title={`Visszajelzések (${feedbacks.length})`}>
          <RelatedTable rows={feedbacks} emptyText="Nincs visszajelzés ehhez az anyaghoz." deleteBasePath={ENTITY_PATHS.feedback} />
        </Card>
      </div>
    </div>
  );
}
