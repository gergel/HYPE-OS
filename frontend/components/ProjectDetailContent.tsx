import {
  Clapperboard,
  FileText,
  Send,
  Users,
  Wallet,
  Wrench,
} from "lucide-react";
import { ActionButton } from "@/components/ActionButton";
import { Card } from "@/components/Card";
import { DeleteButton } from "@/components/DeleteButton";
import { DetailHeader } from "@/components/DetailHeader";
import { DetailSections } from "@/components/DetailSections";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EquipmentBookingManager } from "@/components/EquipmentBookingManager";
import { M2mLinker } from "@/components/M2mLinker";
import { PerformanceCertificateManager } from "@/components/PerformanceCertificateManager";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { RelatedTable } from "@/components/RelatedTable";
import { SubcontractorContractManager } from "@/components/SubcontractorContractManager";
import { TechnikaCheckButton } from "@/components/TechnikaCheckButton";
import { TigInvoiceManager } from "@/components/TigInvoiceManager";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  formatHuf,
  getAllTigForProject,
  getCurrentUser,
  getDetailTabs,
  getEmployees,
  getEquipment,
  getFieldTypes,
  getMyPagePermissions,
  getPendingSubcontractorsForProject,
  getPendingTigForProject,
  getRecord,
  getRelated,
  getSectionOrder,
  getVisibleFields,
} from "@/lib/api";
import { buildFieldTabs, EQUIPMENT_WIDGET_FIELD_KEY } from "@/lib/detailTabs";

// A projekt mezői eredetileg a Notion "Main Database" ~140 oszlopát tükrözik
// (lásd backend/app/models/project.py osztály-kommentje) - ahelyett hogy
// mindezt egyetlen, végtelenül görgetendő listaként dobnánk a felhasználó
// elé, admin által a Beállítások oldalon átrendezhető fülekre osztjuk (lásd
// lib/detailTabs.tsx, backend/app/services/detail_tabs.py). Amit egyik
// konfigurált fül sem tartalmaz, az automatikusan a szintetikus "Egyéb"
// fülre kerül - nem vész el, csak nincs útban a mindennapi használatnál.
/** A Projekt részletnézet TELJES tartalma, külön komponensben, hogy két helyen
 * lehessen ugyanazt megjeleníteni: a rendes /projektek/[id] oldalon, és a
 * lista/naptár nézetből nyíló felugró ablakban (/embed/projektek/[id], amit a
 * ProjectDetailModal tölt be egy iframe-be). A felhasználó kifejezetten a
 * teljes projektet kérte a felugró ablakba, nem egy előnézetet - ez a kettőzés
 * nélküli megoldás, így a két nézet nem tud egymástól elcsúszni.
 *
 * Szerver komponens marad (nem "use client"): a lenti ~14 párhuzamos lekérés
 * szerver-oldali, sütire támaszkodó API hívás, amiket kliens oldalon újra kellene
 * implementálni. `embedded` módban csak az alkalmazás-keret (TopBar, vissza-link)
 * marad el, a tartalom és minden művelet azonos. */
const ALWAYS_HIDDEN = [
  "project_code_id",
  "campaign_id",
  "crew_employee_ids",
  "szerzodes_keszites_employee_id",
  "alvallakozo_keretszerzodes_contract_id",
];

const PAGE = "/projektek";

export async function ProjectDetailContent({ projectId, embedded = false }: { projectId: number; embedded?: boolean }) {
  const project = await getRecord(ENTITY_PATHS.project, projectId);
  if (!project) return null;

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
    allTig,
    visibleFields,
    fieldTypes,
    dbTabs,
    pagePermissions,
    sectionOrder,
    currentUser,
  ] = await Promise.all([
    project.project_code_id ? getRecord(ENTITY_PATHS.projectCode, Number(project.project_code_id)) : null,
    project.campaign_id ? getRecord(ENTITY_PATHS.campaign, Number(project.campaign_id)) : null,
    getRelated(ENTITY_PATHS.deliverable, { project_id: projectId }),
    getEquipment(),
    getEmployees(),
    getRelated(ENTITY_PATHS.assignment, { project_id: projectId }),
    getPendingSubcontractorsForProject(projectId),
    getPendingTigForProject(projectId),
    getAllTigForProject(projectId),
    getVisibleFields("project"),
    getFieldTypes("project"),
    getDetailTabs("project"),
    getMyPagePermissions(),
    getSectionOrder("project"),
    getCurrentUser(),
  ]);

  const employeeNameById = new Map(allEmployees.map((e) => [e.id, e.full_name]));

  const equipmentById = new Map(allEquipment.map((e) => [e.id, e]));
  const equipmentOptions = allEquipment.map((e) => ({
    id: e.id,
    label: e.nev,
    href: `/felszereles/${e.id}`,
    trackMode: e.track_mode,
    kategoria: e.kategoria,
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
    sectionOrder,
    alwaysHidden: ALWAYS_HIDDEN,
    // A lenti bespoke widgetek (diszpó küldés, szerződés/TIG) szándékosan
    // extraTabs-ként, NEM prependContent-ként szerepelnek: a prependContent
    // egy admin által a Beállítások oldalon szabadon átnevezhető/törölhető
    // DB-driven fülhöz (tab_key) tapadt volna - ha admin törölte vagy
    // átszervezte pl. a "technika" fület, a hozzá kötött widget is némán
    // eltűnt, miközben a felhasználó ezt hiányzó funkciónak látta ("nincs
    // opcióm technika hozzáadásához"). Az extraTabs szekciók mindig
    // megjelennek, függetlenül az admin fül-szerkesztésétől.
    //
    // Az Eszközök widget viszont a `widgets` mechanizmuson keresztül kerül
    // be (lásd lib/detailTabs.tsx) - ez is garantáltan sosem tűnik el, de
    // emellett admin a Beállítások > Részletnézet fülek szerkesztőjében
    // szabadon áthelyezheti bármelyik fülre (a EQUIPMENT_WIDGET_FIELD_KEY
    // szintetikus mezőkulcsként viselkedik), és munkatársanként el is
    // rejthető a mező-láthatóság beállítással - pont ezt kérte a
    // felhasználó ("hogy kinél látszódjon és melyik csoportosításba
    // legyen").
    widgets: {
      [EQUIPMENT_WIDGET_FIELD_KEY]: (
        <Card title={`Eszközök (${bookingRows.length})`} icon={Wrench}>
          <EquipmentBookingManager projectId={project.id} bookings={bookingRows} options={equipmentOptions} />
          <div className="mt-4 border-t border-border pt-4">
            <TechnikaCheckButton projectId={project.id} />
          </div>
        </Card>
      ),
    },
    extraTabs: [
      {
        key: "diszpo-kuldes",
        label: "Diszpó küldése",
        content: (
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
      },
      {
        key: "szerzodes-tig",
        label: "Szerződés & TIG",
        content: (
          <>
            <Card title="Szerződés készítés" icon={Wallet}>
              <SubcontractorContractManager projectId={project.id} pending={pendingContracts?.pending ?? []} />
            </Card>
            <Card title="Teljesítési igazolás (Külsős TIG)" icon={FileText}>
              {pendingTig?.tig_ready ? (
                <PerformanceCertificateManager projectId={project.id} pending={pendingTig.pending} />
              ) : (
                <p className="text-[13px] text-text-secondary">
                  Teljesítési igazolás csak azután készíthető, hogy ezen a projekten mindenkinek megvan a szerződés
                  státusza (kiküldve vagy kihagyva) - lásd a fenti &quot;Szerződés készítés&quot; kártyát.
                </p>
              )}
              <TigInvoiceManager
                projectId={project.id}
                basePath="/api/v1/teljesitesi-igazolasok"
                certificates={allTig}
                employeeNameById={employeeNameById}
                readyStatus="Kiküldve"
              />
            </Card>
          </>
        ),
      },
      {
        key: "csapat",
        label: "Csapat & Utómunka",
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
                  redirectPrefix={embedded ? "/embed/utomunka/" : "/utomunka/"}
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
      {!embedded && <TopBar />}
      <div className="flex-1 space-y-6 p-6">
        <DetailHeader
          backHref={embedded ? undefined : "/projektek"}
          backLabel={embedded ? undefined : "Projektek"}
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
                redirectPrefix={embedded ? "/embed/projektek/" : "/projektek/"}
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

        <DetailSections sections={tabs} entityType="project" canReorder={currentUser?.role === "admin"} />
      </div>
    </div>
  );
}
