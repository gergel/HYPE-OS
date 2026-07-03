import { notFound } from "next/navigation";
import { ActionButton } from "@/components/ActionButton";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailGrid } from "@/components/DetailGrid";
import { EquipmentBookingManager } from "@/components/EquipmentBookingManager";
import { M2mLinker } from "@/components/M2mLinker";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { RelatedTable } from "@/components/RelatedTable";
import { SingleRelationPicker } from "@/components/SingleRelationPicker";
import { TechnikaCheckButton } from "@/components/TechnikaCheckButton";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getContracts, getEmployees, getEquipment, getRecord, getRelated } from "@/lib/api";
import { toDetailFields } from "@/lib/detail";

export default async function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectId = Number(id);
  const project = await getRecord(ENTITY_PATHS.project, projectId);
  if (!project) notFound();

  const crewIds = Array.isArray(project.crew_employee_ids) ? (project.crew_employee_ids as number[]) : [];

  const [projectCode, campaign, deliverables, allEquipment, allEmployees, bookings, allContracts] = await Promise.all([
    project.project_code_id ? getRecord(ENTITY_PATHS.projectCode, Number(project.project_code_id)) : null,
    project.campaign_id ? getRecord(ENTITY_PATHS.campaign, Number(project.campaign_id)) : null,
    getRelated(ENTITY_PATHS.deliverable, { project_id: projectId }),
    getEquipment(),
    getEmployees(),
    getRelated(ENTITY_PATHS.assignment, { project_id: projectId }),
    getContracts(),
  ]);

  const equipmentById = new Map(allEquipment.map((e) => [e.id, e]));
  const equipmentOptions = allEquipment.map((e) => ({
    id: e.id,
    label: e.nev,
    href: `/felszereles/${e.id}`,
    trackMode: e.track_mode,
  }));
  const crewOptions = allEmployees.map((e) => ({ id: e.id, label: e.full_name, href: `/csapat/${e.id}` }));
  const contractOptions = allContracts
    .filter((c) => c.tipus === "alvallalkozoi")
    .map((c) => ({ id: c.id, label: c.ceg_neve || `Szerződés #${c.id}` }));

  const bookingRows = bookings
    .map((b) => {
      const equipmentId = Number(b.equipment_id);
      const equipment = equipmentById.get(equipmentId);
      if (!equipment) return null;
      return {
        id: Number(b.id),
        label: equipment.nev,
        href: `/felszereles/${equipment.id}`,
        qty: Number(b.qty ?? 1),
        trackMode: equipment.track_mode,
      };
    })
    .filter((b): b is NonNullable<typeof b> => b !== null);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/projektek" label="Projektek" />

        <Card title={String(project.nev ?? `Projekt #${project.id}`)}>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
            <div className="flex flex-wrap gap-4 text-[13px] text-text-secondary">
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
            <ActionButton
              path={`/api/v1/projects/${project.id}/feldarabolas`}
              label="Feldarabolás"
              confirmMessage="Új projekt jön létre ugyanahhoz a Project Code-hoz (feldarabolt forgatási nap). Folytatod?"
              redirectPrefix="/projektek/"
            />
          </div>
          <DetailGrid
            fields={toDetailFields(project, [
              "project_code_id",
              "campaign_id",
              "crew_employee_ids",
              "szerzodes_keszites_employee_id",
              "alvallakozo_keretszerzodes_contract_id",
            ])}
          />
        </Card>

        <Card title="Diszpó">
          <div className="flex flex-wrap items-center gap-3">
            <ActionButton
              path={`/api/v1/projects/${project.id}/diszpo/elozetes`}
              label="Előzetes diszpó"
              confirmMessage="Elküldi az előzetes diszpót a résztvevőknek. Folytatod?"
            />
            <ActionButton
              path={`/api/v1/projects/${project.id}/diszpo/kuldes`}
              label="Diszpó küldése"
              confirmMessage="Elküldi a teljes diszpót (technika listával, PDF-fel) a résztvevőknek. Folytatod?"
            />
            <span className="text-[13px] text-text-secondary">
              Diszpó állapot: {String(project.diszpo ?? "–")} · Előzetes: {String(project.elozetes_diszpo_kuldes ?? "–")}
            </span>
          </div>
        </Card>

        <Card title="Szerződés">
          <div className="space-y-4">
            <div>
              <p className="mb-2 text-[13px] font-medium text-text-primary">Szerződés készítés (megbízott kiválasztása)</p>
              <SingleRelationPicker
                path={`/api/v1/projects/${project.id}/szerzodes-keszites`}
                bodyKey="employee_id"
                currentId={project.szerzodes_keszites_employee_id as number | null}
                currentLabel={project.megbizott_neve as string | null}
                options={crewOptions}
                actionLabel="Adatok átemelése"
                emptyText="Nincs kiválasztva megbízott."
                allowClear={false}
              />
            </div>
            <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
              <ActionButton
                path={`/api/v1/projects/${project.id}/szerzodes-keszites-es-kuldese`}
                label="Szerződés készítése és küldése"
                confirmMessage="Elküldi a megbízási szerződést a kiválasztott megbízott email címére. Folytatod?"
              />
              <span className="text-[13px] text-text-secondary">Állapot: {String(project.szerzodes_allapot ?? "–")}</span>
            </div>
            <div className="border-t border-border pt-4">
              <p className="mb-2 text-[13px] font-medium text-text-primary">Alvállakozó keretszerződés (külsős)</p>
              <SingleRelationPicker
                path={`${ENTITY_PATHS.project}/${project.id}`}
                method="PATCH"
                bodyKey="alvallakozo_keretszerzodes_contract_id"
                currentId={project.alvallakozo_keretszerzodes_contract_id as number | null}
                options={contractOptions}
                actionLabel="Hozzálinkelés"
                emptyText="Nincs hozzálinkelt keretszerződés."
              />
            </div>
          </div>
        </Card>

        <Card title={`Eszközök (${bookingRows.length})`}>
          <EquipmentBookingManager projectId={project.id} bookings={bookingRows} options={equipmentOptions} />
          <div className="mt-4 border-t border-border pt-4">
            <TechnikaCheckButton projectId={project.id} />
          </div>
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
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <ActionButton
              path={`/api/v1/projects/${project.id}/create-utomunka`}
              label="+ Utómunka létrehozása"
              redirectPrefix="/utomunka/"
            />
            <span className="text-[13px] text-text-secondary">
              Automatikusan névvel és forgatáshoz kötve jön létre (Notion automatizmus alapján).
            </span>
          </div>
          <QuickCreateForm
            postPath={ENTITY_PATHS.deliverable}
            addLabel="+ Egyéni utómunka hozzáadása"
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
