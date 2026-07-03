import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailGrid } from "@/components/DetailGrid";
import { M2mLinker } from "@/components/M2mLinker";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getEmployees, getEquipment, getRecord, getRelated } from "@/lib/api";
import { toDetailFields } from "@/lib/detail";

export default async function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectId = Number(id);
  const project = await getRecord(ENTITY_PATHS.project, projectId);
  if (!project) notFound();

  const equipmentIds = Array.isArray(project.equipment_ids) ? (project.equipment_ids as number[]) : [];
  const crewIds = Array.isArray(project.crew_employee_ids) ? (project.crew_employee_ids as number[]) : [];

  const [projectCode, campaign, deliverables, allEquipment, allEmployees] = await Promise.all([
    project.project_code_id ? getRecord(ENTITY_PATHS.projectCode, Number(project.project_code_id)) : null,
    project.campaign_id ? getRecord(ENTITY_PATHS.campaign, Number(project.campaign_id)) : null,
    getRelated(ENTITY_PATHS.deliverable, { project_id: projectId }),
    getEquipment(),
    getEmployees(),
  ]);

  const equipmentOptions = allEquipment.map((e) => ({ id: e.id, label: e.nev, href: `/felszereles/${e.id}` }));
  const crewOptions = allEmployees.map((e) => ({ id: e.id, label: e.full_name, href: `/csapat/${e.id}` }));

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
          <DetailGrid
            fields={toDetailFields(project, ["project_code_id", "campaign_id", "equipment_ids", "crew_employee_ids"])}
          />
        </Card>

        <Card title={`Eszközök (${equipmentIds.length})`}>
          <M2mLinker
            patchPath={`${ENTITY_PATHS.project}/${project.id}`}
            fieldName="equipment_ids"
            currentIds={equipmentIds}
            options={equipmentOptions}
            emptyText="Nincs eszköz hozzárendelve ehhez a projekthez."
            addLabel="Eszköz hozzáadása"
          />
        </Card>

        <Card title={`Stáb (${crewIds.length})`}>
          <M2mLinker
            patchPath={`${ENTITY_PATHS.project}/${project.id}`}
            fieldName="crew_employee_ids"
            currentIds={crewIds}
            options={crewOptions}
            emptyText="Nincs stábtag hozzárendelve ehhez a projekthez."
            addLabel="Stábtag hozzáadása"
          />
        </Card>

        <Card title={`Utómunka (${deliverables.length})`}>
          <QuickCreateForm
            postPath={ENTITY_PATHS.deliverable}
            addLabel="+ Új utómunka hozzáadása"
            presetFields={{ project_id: project.id, project_code_id: project.project_code_id }}
            fields={[
              { name: "projekt_neve", label: "Anyag neve", required: true },
              { name: "allapot", label: "Állapot" },
              { name: "hatarido", label: "Határidő", type: "date" },
            ]}
          />
          <RelatedTable
            rows={deliverables}
            emptyText="Nincs vágandó anyag ehhez a projekthez."
            getHref={(d) => `/utomunka/${d.id}`}
            deleteBasePath={ENTITY_PATHS.deliverable}
          />
        </Card>
      </div>
    </div>
  );
}
