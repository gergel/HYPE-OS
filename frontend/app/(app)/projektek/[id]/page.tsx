import { notFound } from "next/navigation";
import { Clapperboard, FileText, Send, Users, Wallet, Wrench } from "lucide-react";
import { ActionButton } from "@/components/ActionButton";
import { Card } from "@/components/Card";
import { DeleteButton } from "@/components/DeleteButton";
import { DetailHeader } from "@/components/DetailHeader";
import { DetailTabs } from "@/components/DetailTabs";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EquipmentBookingManager } from "@/components/EquipmentBookingManager";
import { M2mLinker } from "@/components/M2mLinker";
import { PerformanceCertificateManager } from "@/components/PerformanceCertificateManager";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { RelatedTable } from "@/components/RelatedTable";
import { SubcontractorContractManager } from "@/components/SubcontractorContractManager";
import { TechnikaCheckButton } from "@/components/TechnikaCheckButton";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  formatHuf,
  getDetailTabs,
  getEmployees,
  getEquipment,
  getFieldTypes,
  getMyPagePermissions,
  getPendingSubcontractorsForProject,
  getPendingTigForProject,
  getRecord,
  getRelated,
  getVisibleFields,
} from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";

// A projekt mezői eredetileg a Notion "Main Database" ~140 oszlopát tükrözik
// (lásd backend/app/models/project.py osztály-kommentje) - ahelyett hogy
// mindezt egyetlen, végtelenül görgetendő listaként dobnánk a felhasználó
// elé, admin által a Beállítások oldalon átrendezhető fülekre osztjuk (lásd
// lib/detailTabs.tsx, backend/app/services/detail_tabs.py). Amit egyik
// konfigurált fül sem tartalmaz, az automatikusan a szintetikus "Egyéb"
// fülre kerül - nem vész el, csak nincs útban a mindennapi használatnál.
const ALWAYS_HIDDEN = [
  "project_code_id",
  "campaign_id",
  "crew_employee_ids",
  "szerzodes_keszites_employee_id",
  "alvallakozo_keretszerzodes_contract_id",
];

const PAGE = "/projektek";

export default async function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectId = Number(id);
  const project = await getRecord(ENTITY_PATHS.project, projectId);
  if (!project) notFound();

  const crewIds = Array.isArray(project.crew_employee_ids) ? (project.crew_employee_ids as number[]) : [];

  const [
    projectCode,
    campaign,
    deliverables,
    allEquipment,
    allEmployees,
    bookings,
    pendingContracts,
    pendingTig,
    visibleFields,
    fieldTypes,
    dbTabs,
    pagePermissions,
  ] = await Promise.all([
    project.project_code_id ? getRecord(ENTITY_PATHS.projectCode, Number(project.project_code_id)) : null,
    project.campaign_id ? getRecord(ENTITY_PATHS.campaign, Number(project.campaign_id)) : null,
    getRelated(ENTITY_PATHS.deliverable, { project_id: projectId }),
    getEquipment(),
    getEmployees(),
    getRelated(ENTITY_PATHS.assignment, { project_id: projectId }),
    getPendingSubcontractorsForProject(projectId),
    getPendingTigForProject(projectId),
    getVisibleFields("project"),
    getFieldTypes("project"),
    getDetailTabs("project"),
    getMyPagePermissions(),
  ]);

  const equipmentById = new Map(allEquipment.map((e) => [e.id, e]));
  const equipmentOptions = allEquipment.map((e) => ({
    id: e.id,
    label: e.nev,
    href: `/felszereles/${e.id}`,
    trackMode: e.track_mode,
  }));
  const crewOptions = allEmployees.map((e) => ({ id: e.id, label: e.full_name, href: `/csapat/${e.id}` }));

  const deliverableTimesheets = await Promise.all(
    deliverables.map((d) => getRelated(ENTITY_PATHS.timesheet, { deliverable_id: Number(d.id) })),
  );
  const vagasiKoltsegOsszesen = deliverableTimesheets
    .flat()
    .reduce((sum, t) => sum + (typeof t.koltseg === "number" ? t.koltseg : 0), 0);

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

  const patchPath = `${ENTITY_PATHS.project}/${project.id}`;

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath,
    record: project,
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
    alwaysHidden: ALWAYS_HIDDEN,
    badges: { technika: bookingRows.length },
    prependContent: {
      diszpo: (
        <Card title="Diszpó küldése" icon={Send}>
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
          </div>
        </Card>
      ),
      technika: (
        <Card title={`Eszközök (${bookingRows.length})`} icon={Wrench}>
          <EquipmentBookingManager projectId={project.id} bookings={bookingRows} options={equipmentOptions} />
          <div className="mt-4 border-t border-border pt-4">
            <TechnikaCheckButton projectId={project.id} />
          </div>
        </Card>
      ),
      penzugy: (
        <>
          <Card title="Szerződés készítés" icon={Wallet}>
            <SubcontractorContractManager projectId={project.id} pending={pendingContracts?.pending ?? []} />
          </Card>
          <Card title="Teljesítési igazolás" icon={FileText}>
            {pendingTig?.tig_ready ? (
              <PerformanceCertificateManager projectId={project.id} pending={pendingTig.pending} />
            ) : (
              <p className="text-[13px] text-text-secondary">
                Teljesítési igazolás csak azután készíthető, hogy ezen a projekten mindenkinek megvan a szerződés
                státusza (kiküldve vagy kihagyva) - lásd a fenti "Szerződés készítés" kártyát.
              </p>
            )}
          </Card>
        </>
      ),
    },
    extraTabs: [
      {
        key: "csapat",
        label: "Csapat & Utómunka",
        badge: crewIds.length + deliverables.length,
        content: (
          <>
            <Card title={`Stáb (${crewIds.length})`} icon={Users}>
              <M2mLinker
                patchPath={patchPath}
                fieldName="crew_employee_ids"
                currentIds={crewIds}
                options={crewOptions}
                emptyText="Nincs stábtag hozzárendelve ehhez a projekthez."
                addLabel="Stábtag hozzáadása"
              />
            </Card>
            <Card title={`Utómunka (${deliverables.length})`} icon={Clapperboard}>
              {deliverables.length > 0 && (
                <p className="mb-3 text-[13px] text-text-secondary">
                  Vágási költség összesen: <span className="font-medium text-text-primary">{formatHuf(vagasiKoltsegOsszesen)}</span>
                </p>
              )}
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
          </>
        ),
      },
    ],
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <DetailHeader
          backHref="/projektek"
          backLabel="Projektek"
          title={String(project.nev ?? `Projekt #${project.id}`)}
          statusBadge={
            <EditableStatusBadge
              patchPath={patchPath}
              field="allapot"
              value={project.allapot ? String(project.allapot) : null}
              options={fieldTypes.allapot?.options ?? []}
            />
          }
          subtitle={
            <>
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
            </>
          }
          actions={
            <>
              <ActionButton
                path={`/api/v1/projects/${project.id}/feldarabolas`}
                label="Feldarabolás"
                confirmMessage="Új projekt jön létre ugyanahhoz a Project Code-hoz (feldarabolt forgatási nap). Folytatod?"
                redirectPrefix="/projektek/"
              />
              <DeleteButton
                path={patchPath}
                redirectTo="/projektek"
                label="Törlés"
                className="rounded-[var(--radius)] border border-text-danger/40 px-3 py-1.5 text-[13px] text-text-danger transition-colors hover:bg-bg-danger disabled:opacity-50"
              />
            </>
          }
        />

        <DetailTabs tabs={tabs} />
      </div>
    </div>
  );
}
