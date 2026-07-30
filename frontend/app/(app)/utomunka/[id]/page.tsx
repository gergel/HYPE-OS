import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { AssignedToPicker } from "@/components/deliverable/AssignedToPicker";
import { CommentsSection } from "@/components/deliverable/CommentsSection";
import { ContactsManager } from "@/components/deliverable/ContactsManager";
import { CreatePortalButton } from "@/components/deliverable/CreatePortalButton";
import { FeedbackSendButton } from "@/components/deliverable/FeedbackSendButton";
import { TimerControls } from "@/components/deliverable/TimerControls";
import { VinyokEditor } from "@/components/deliverable/VinyokEditor";
import { DetailSections } from "@/components/DetailSections";
import { RelatedTable } from "@/components/RelatedTable";
import { TimesheetMinutesTable } from "@/components/deliverable/TimesheetMinutesTable";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getAssignableEmployees,
  getContactsByClient,
  getDeliverableComments,
  getDeliverableContacts,
  getEmployees,
  getDetailTabs,
  getFieldTypes,
  getMyPagePermissions,
  getRecord,
  getRelated,
  getTimerState,
  getVinyoOptions,
  getVisibleFields,
} from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";

const HIDDEN_FIELDS = [
  "project_code_id",
  "project_id",
  "vago_employee_id",
  "campaign_id",
  "aki_felvezette_employee_id",
  "assigned_to_employee_id",
  "vinyok",
  "megrendeloi_kontaktok_notion_ids",
  "megrendeloi_email_cimek",
  "aki_felvezette_az_utomunkat_notion_ids",
  "aki_ellenorzesbe_tette_notion_ids",
  "assigned_to_notion",
  "visszajelzessek_notion_ids",
  "timesheet_public_notion_ids",
  "timesheet_private_notion_ids",
  "total_time",
  "stop_timer",
  "portal_id",
];

const PAGE = "/utomunka";

export default async function DeliverableDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const deliverableId = Number(id);
  const deliverable = await getRecord(ENTITY_PATHS.deliverable, deliverableId);
  if (!deliverable) notFound();

  const [
    projectCode,
    project,
    vago,
    campaign,
    felvezeto,
    timesheets,
    feedbacks,
    visibleFields,
    fieldTypes,
    assignableEmployees,
    vinyoOptions,
    contacts,
    timerState,
    comments,
    dbTabs,
    pagePermissions,
    allEmployees,
  ] = await Promise.all([
    deliverable.project_code_id ? getRecord(ENTITY_PATHS.projectCode, Number(deliverable.project_code_id)) : null,
    deliverable.project_id ? getRecord(ENTITY_PATHS.project, Number(deliverable.project_id)) : null,
    deliverable.vago_employee_id ? getRecord(ENTITY_PATHS.employee, Number(deliverable.vago_employee_id)) : null,
    deliverable.campaign_id ? getRecord(ENTITY_PATHS.campaign, Number(deliverable.campaign_id)) : null,
    deliverable.aki_felvezette_employee_id ? getRecord(ENTITY_PATHS.employee, Number(deliverable.aki_felvezette_employee_id)) : null,
    getRelated(ENTITY_PATHS.timesheet, { deliverable_id: deliverableId }),
    getRelated(ENTITY_PATHS.feedback, { deliverable_id: deliverableId }),
    getVisibleFields("deliverable"),
    getFieldTypes("deliverable"),
    getAssignableEmployees(),
    getVinyoOptions(),
    getDeliverableContacts(deliverableId),
    getTimerState(deliverableId),
    getDeliverableComments(deliverableId),
    getDetailTabs("deliverable"),
    getMyPagePermissions(),
    getEmployees(),
  ]);

  const clientId = projectCode ? Number(projectCode.client_id) : null;
  const contactOptions = clientId ? await getContactsByClient(clientId) : [];

  const employeeNameById = Object.fromEntries(allEmployees.map((e) => [e.id, e.full_name]));
  // Aki az Utómunka oldalon szerkeszthet, az javíthatja a rögzített perceket is.
  const canEditPage = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");
  // Forint összeg csak annak, akinek a Pénzügy oldalhoz van hozzáférése.
  const canSeeCost = pagePermissions === null || !!pagePermissions["/penzugyek"]?.includes("view");

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath: `${ENTITY_PATHS.deliverable}/${deliverable.id}`,
    record: deliverable,
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
    alwaysHidden: HIDDEN_FIELDS,
    extraTabs: [
      {
        key: "kiosztas",
        label: "Kiosztás",
        content: (
          <Card title="Kiosztás">
            <p className="mb-2 text-[13px] text-text-secondary">
              Kire van kiosztva ez a vágás - csak azok közül választhatsz, akiknek van bejelentkezési joga az Utómunka oldalhoz.
            </p>
            <AssignedToPicker
              deliverableId={deliverableId}
              employees={assignableEmployees}
              currentId={deliverable.assigned_to_employee_id ? Number(deliverable.assigned_to_employee_id) : null}
            />
          </Card>
        ),
      },
      {
        key: "kontaktok",
        label: "Megrendelői kontaktok",
        content: (
          <Card title="Megrendelői kontaktok">
            <p className="mb-2 text-[13px] text-text-secondary">Kinek kell kiküldeni a kész anyagot.</p>
            <ContactsManager deliverableId={deliverableId} current={contacts} options={contactOptions} />
            {deliverable.megrendeloi_email_cimek != null && (
              <p className="mt-3 text-[12px] text-text-muted">
                Email címek: <span className="text-text-secondary">{String(deliverable.megrendeloi_email_cimek)}</span>
              </p>
            )}
          </Card>
        ),
      },
      {
        key: "media-portal",
        label: "Média Portál",
        content: (
          <Card title="Média Portál">
            <CreatePortalButton
              deliverableId={deliverableId}
              existingPortalId={deliverable.portal_id ? Number(deliverable.portal_id) : null}
              keszAnyagUrl={deliverable.kesz_anyag_url ? String(deliverable.kesz_anyag_url) : null}
            />
          </Card>
        ),
      },
      {
        key: "vinyok",
        label: "Vinyók",
        content: (
          <Card title="Vinyók">
            <VinyokEditor
              deliverableId={deliverableId}
              knownOptions={vinyoOptions}
              currentValues={Array.isArray(deliverable.vinyok) ? (deliverable.vinyok as string[]) : []}
            />
          </Card>
        ),
      },
      {
        key: "idomeres",
        label: "Időmérés",
        content: (
          <Card title="Időmérés">
            <TimerControls deliverableId={deliverableId} initialState={timerState} showCost={canSeeCost} />
          </Card>
        ),
      },
      {
        key: "munkaido",
        label: "Munkaidő-elszámolások",
        content: (
          <Card title={`Munkaidő-elszámolások (${timesheets.length})`}>
            {/* A perc helyben javítható - ha valaki elfelejti leállítani az
                időmérőt, enélkül egy egész éjszakányi idő maradna a soron (és
                az abból számolt költség a Pénzügyben). */}
            <TimesheetMinutesTable
              deliverableId={deliverableId}
              rows={timesheets}
              employeeNameById={employeeNameById}
              canEdit={canEditPage}
              showCost={canSeeCost}
            />
          </Card>
        ),
      },
      {
        key: "visszajelzesek",
        label: "Visszajelzések",
        content: (
          <Card title={`Visszajelzések (${feedbacks.length})`}>
            <div className="mb-3">
              <FeedbackSendButton deliverableId={deliverableId} />
            </div>
            <RelatedTable
              rows={feedbacks}
              emptyText="Nincs visszajelzés ehhez az anyaghoz."
              entityKey="feedback"
              deleteBasePath={ENTITY_PATHS.feedback}
            />
          </Card>
        ),
      },
      {
        key: "hozzaszolasok",
        label: "Hozzászólások",
        content: (
          <Card title="Hozzászólások">
            <CommentsSection deliverableId={deliverableId} initialComments={comments} mentionableEmployees={assignableEmployees} />
          </Card>
        ),
      },
    ],
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/utomunka" label="Utómunka" />
        <h1 className="text-lg font-medium text-text-primary">{String(deliverable.projekt_neve ?? `Anyag #${deliverable.id}`)}</h1>
        <div className="flex flex-wrap gap-4 text-[13px] text-text-secondary">
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
          {felvezeto && (
            <a href={`/csapat/${felvezeto.id}`} className="text-text-accent hover:underline">
              Felvezette: {String(felvezeto.full_name)}
            </a>
          )}
        </div>

        <DetailSections sections={tabs} />
      </div>
    </div>
  );
}
