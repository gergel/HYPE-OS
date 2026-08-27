import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { AllapotValaszto } from "@/components/deliverable/AllapotValaszto";
import { AssignedToPicker } from "@/components/deliverable/AssignedToPicker";
import { CommentsSection } from "@/components/deliverable/CommentsSection";
import { ContactsManager } from "@/components/deliverable/ContactsManager";
import { CreatePortalButton } from "@/components/deliverable/CreatePortalButton";
import { FeedbackSendButton } from "@/components/deliverable/FeedbackSendButton";
import { VisszajelzesLista } from "@/components/deliverable/VisszajelzesLista";
import { TimerControls } from "@/components/deliverable/TimerControls";
import { VinyokEditor } from "@/components/deliverable/VinyokEditor";
import { DetailSections } from "@/components/DetailSections";
import { RelatedTable } from "@/components/RelatedTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TimesheetMinutesTable } from "@/components/deliverable/TimesheetMinutesTable";
import { szerepkorei } from "@/lib/permissions";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getAssignableEmployees,
  getMegrendeloiKontaktok,
  getVagoiVisszajelzesek,
  getDeliverableComments,
  getDeliverableContacts,
  getCurrentUser,
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
import { formatIdopont } from "@/lib/ido";

const HIDDEN_FIELDS = [
  "project_code_id",
  "project_id",
  "vago_employee_id",
  "campaign_id",
  "aki_felvezette_employee_id",
  "assigned_to_employee_id",
  // A "Kiküldve" jelzőt a lista Kiküldve oszlopa mutatja (StatusBadge) - itt,
  // az "Egyéb" kártyán külön mezőként semmi hasznot nem adna, csak zajt.
  "anyag_kikuldve",
  // Az "allapot" a generikus EditableDetailGrid helyett a bespoke
  // AllapotValaszto komponensen keresztül szerkeszthető (lásd fent a fejlécnél) -
  // ANNAK muszáj felismernie az "Ellenőrzésbe" váltás visszajelzés-hiányát és
  // felugró űrlapot nyitnia helyette, amit a generikus mező-rács nem tud
  // (az BÁRMELYIK entitáshoz szól, nem ismerhet Deliverable-specifikus
  // szabályt).
  "allapot",
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
    currentUser,
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
    getCurrentUser(),
  ]);

  const clientId = projectCode ? Number(projectCode.client_id) : null;
  // MINDEN megrendelői kontakt a választék, nem csak az anyag ügyfeléé: egy
  // kész anyagot gyakran olyanoknak is ki kell küldeni, akik máshol vannak
  // (ügynökség, társproducer). A saját ügyfél kontaktjai a lista elejére
  // kerülnek (lásd ContactsManager).
  const contactOptions = await getMegrendeloiKontaktok();
  // A visszajelzések saját, részletes alakja (ki írta, mikor, pontszámok) -
  // a nyers `feedbacks` sorokból ez nem állna elő.
  const vagoiVisszajelzesek = await getVagoiVisszajelzesek(deliverableId);

  const employeeNameById = Object.fromEntries(allEmployees.map((e) => [e.id, e.full_name]));
  const statusOptions = fieldTypes.allapot?.options ?? [];
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
            <ContactsManager
              deliverableId={deliverableId}
              current={contacts}
              options={contactOptions}
              clientId={clientId}
            />
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
            <TimerControls
              deliverableId={deliverableId}
              initialState={timerState}
              showCost={canSeeCost}
              isAdmin={szerepkorei(currentUser).includes("admin")}
            />
            {/* Mikor állították le utoljára a mérőt. A Notionból importált
                anyagoknál ez a 'Timesheet Public' End Date mezője - ott van az
                egyetlen nyoma annak, mikor fejezték be a vágást. */}
            <p className="mt-3 border-t border-border pt-3 text-[13px] text-text-secondary">
              Vágás leállítva:{" "}
              <span className="text-text-primary">
                {formatIdopont(typeof deliverable.vagas_leallitva === "string" ? deliverable.vagas_leallitva : null)}
              </span>
            </p>
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
              koltsegById={timerState?.sor_koltsegek ?? {}}
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
          <Card title={`Visszajelzések (${vagoiVisszajelzesek.length})`}>
            <div className="mb-3">
              <FeedbackSendButton deliverableId={deliverableId} />
            </div>
            {/* A generikus kapcsolt-tábla helyett a visszajelzés SAJÁT
                nézete: ott a pontszám, a megjegyzés, és - ami a lényeg -
                hogy KI írta és MIKOR (lásd VisszajelzesLista). */}
            <VisszajelzesLista
              visszajelzesek={vagoiVisszajelzesek}
              canSend={canEditPage}
              canDelete={canEditPage}
              kompakt
            />
          </Card>
        ),
      },
    ],
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <div className="space-y-2">
          <BackLink href="/utomunka" label="Utómunka" />
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="t-page">{String(deliverable.projekt_neve ?? `Anyag #${deliverable.id}`)}</h1>
            {/* Bespoke szerkesztő, nem a generikus mező-rács (lásd
                HIDDEN_FIELDS "allapot" bejegyzését fent): ez ismeri fel, ha
                a szerver visszajelzés hiánya miatt utasítja el az
                Ellenőrzésbe tételt, és felugró űrlapot nyit helyette. */}
            {canEditPage ? (
              <AllapotValaszto
                deliverableId={deliverableId}
                allapot={deliverable.allapot ? String(deliverable.allapot) : null}
                options={statusOptions}
              />
            ) : (
              Boolean(deliverable.allapot) && <StatusBadge label={String(deliverable.allapot)} tone="neutral" />
            )}
          </div>
        </div>
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

        <DetailSections
          sections={tabs}
          entityType="deliverable"
          canReorder={szerepkorei(currentUser).includes("admin")}
        />

        {/* A hozzászólások SZÁNDÉKOSAN nem a fenti, átrendezhető kártyák
            közt élnek: azok a több-oszlopos "masonry" elrendezésben
            keskenyebbek lennének, és a sorrend is a beállítástól függene -
            egy beszélgetés viszont mindig ugyanott, teljes szélességben, a
            lap alján a legjobb, hogy könnyű legyen rátalálni és olvasni. */}
        <Card title="Hozzászólások">
          <CommentsSection deliverableId={deliverableId} initialComments={comments} mentionableEmployees={assignableEmployees} />
        </Card>
      </div>
    </div>
  );
}
