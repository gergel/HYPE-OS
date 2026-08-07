import {
  Clapperboard,
  FileText,
  Paperclip,
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
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { EquipmentBookingManager } from "@/components/EquipmentBookingManager";
import { ForgatasIdopontEditor } from "@/components/ForgatasIdopontEditor";
import { M2mLinker } from "@/components/M2mLinker";
import { PerformanceCertificateManager } from "@/components/PerformanceCertificateManager";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { RelatedTable } from "@/components/RelatedTable";
import { SubcontractorContractManager } from "@/components/SubcontractorContractManager";
import { ElkeszultSzerzodesek } from "@/components/ElkeszultSzerzodesek";
import { TechnikaCheckButton } from "@/components/TechnikaCheckButton";
import { TigInvoiceManager } from "@/components/TigInvoiceManager";
import { szerepkorei } from "@/lib/permissions";
import { TopBar } from "@/components/TopBar";
import { VagasiKoltsegOsszesen, type FutoMeres } from "@/components/deliverable/VagasiKoltsegOsszesen";
import {
  ENTITY_PATHS,
  getAllContractsForProject,
  getAllTigForProject,
  getAttachments,
  getCurrentUser,
  getDetailTabs,
  getEmployees,
  getEquipment,
  getFieldTypes,
  getMyPagePermissions,
  getPendingSubcontractorsForProject,
  getPendingTigForProject,
  getProjektUtomunkaOsszesites,
  getRecord,
  getRelated,
  getSectionOrder,
  getVisibleFields,
} from "@/lib/api";
import { buildFieldTabs, EQUIPMENT_WIDGET_FIELD_KEY, FORGATAS_IDOPONT_WIDGET_FIELD_KEY } from "@/lib/detailTabs";
import { formatFt, formatPercek } from "@/lib/ido";

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
  // A forgatás dátuma/időpontja NEM külön mezőkként, hanem egy összevont
  // widgetben szerkeszthető (lásd ForgatasIdopontEditor) - egy dolgot írnak le,
  // és így nem lehet a kezdést a végétől külön elrontani.
  "forgatas_datuma",
  "forgatas_datuma_vege",
  "forgatas_kezdes_ido",
  "forgatas_veg_ido",
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
    osszesSzerzodes,
    visibleFields,
    fieldTypes,
    dbTabs,
    pagePermissions,
    sectionOrder,
    currentUser,
    attachments,
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
    getAllContractsForProject(projectId),
    getVisibleFields("project"),
    getFieldTypes("project"),
    getDetailTabs("project"),
    getMyPagePermissions(),
    getSectionOrder("project"),
    getCurrentUser(),
    getAttachments("project", projectId),
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
  // A típus csoportosít, az e-mail pedig segít megkülönböztetni az azonos nevű
  // embereket a stábtag-kereső listájában (lásd M2mLinker + SearchableIdPicker).
  const crewOptions = allEmployees.map((e) => ({
    id: e.id,
    label: e.full_name,
    href: `/csapat/${e.id}`,
    sublabel: e.email,
    group: e.tipus,
  }));

  // Az utómunka-idő és -költség összesítése a SZERVERRŐL jön (egy hívás,
  // anyagonkénti lekérdezések nélkül): a soron rögzített összeg gyakran
  // hiányzik, olyankor az időből és az órabérből számol - ugyanazzal a
  // szabállyal, mint az anyag oldala, hogy a két helyen ne álljon más szám.
  // A MÉG FUTÓ méréseket a VagasiKoltsegOsszesen adja hozzá másodpercenként.
  const utomunkaOsszesites = await getProjektUtomunkaOsszesites(Number(project.id));
  const futoMeresek: FutoMeres[] = (utomunkaOsszesites?.futok ?? []).map((f) => ({
    since: f.since,
    orabere: f.orabere,
  }));
  const lezartPercek = utomunkaOsszesites?.total_minutes ?? 0;
  const lezartKoltseg = utomunkaOsszesites?.total_cost ?? 0;
  const vagokBontasa = utomunkaOsszesites?.by_employee ?? [];
  // A forint összeg itt is a Pénzügy-hozzáféréshez kötött (ugyanaz a szabály,
  // mint az Utómunka oldalon - lásd deliverable_actions._may_see_costs).
  const lathatKoltseget = pagePermissions === null || !!pagePermissions["/penzugyek"]?.includes("view");
  // A diszpó-mellékleteket az szerkesztheti, aki a Projekteket is - ugyanaz a
  // jog, amit a backend is ellenőriz (services/attachments.py ENTITAS_OLDALAK).
  const szerkeszthet = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");
  const torolhet = pagePermissions === null || !!pagePermissions[PAGE]?.includes("delete");

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

  // A két diszpó-állapot csak visszajelzésként jelenik meg a küldés-gombok
  // mellett (lásd a "diszpo-kuldes" fület lentebb) - a rekord JsonRecord, ezért
  // itt szűkítjük szöveggé.
  const asText = (value: unknown) => (typeof value === "string" ? value : "");
  const elozetesAllapot = typeof project.elozetes_diszpo_kuldes === "string" ? project.elozetes_diszpo_kuldes : null;
  const diszpoAllapot = typeof project.diszpo === "string" ? project.diszpo : null;

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
      [FORGATAS_IDOPONT_WIDGET_FIELD_KEY]: (
        <ForgatasIdopontEditor
          patchPath={patchPath}
          initial={{
            start: asText(project.forgatas_datuma),
            startTime: asText(project.forgatas_kezdes_ido).slice(0, 5),
            end: asText(project.forgatas_datuma_vege),
            endTime: asText(project.forgatas_veg_ido).slice(0, 5),
          }}
          readOnly={pagePermissions !== null && !(pagePermissions[PAGE] ?? []).includes("edit")}
        />
      ),
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
        // A gomb mellett látszik, hogy az adott diszpó már kiment-e. Ez
        // szándékosan NEM szerkeszthető (StatusBadge, nem EditableStatusBadge):
        // az állapotot kizárólag a tényleges kiküldés állíthatja, itt csak
        // visszajelzés.
        content: (
          <>
            <Card title="Diszpó küldése" icon={Send}>
              <div className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <ActionButton
                    path={`/api/v1/projects/${project.id}/diszpo/elozetes`}
                    label="Előzetes diszpó"
                    confirmMessage="Elküldi az előzetes diszpót a résztvevőknek. Folytatod?"
                  />
                  {elozetesAllapot && <StatusBadge label={elozetesAllapot} tone="success" />}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <ActionButton
                    path={`/api/v1/projects/${project.id}/diszpo/kuldes`}
                    label="Diszpó küldése"
                    confirmMessage="Elküldi a teljes diszpót (technika listával, PDF-fel) a résztvevőknek. Folytatod?"
                  />
                  {diszpoAllapot && <StatusBadge label={diszpoAllapot} tone="success" />}
                </div>
              </div>
            </Card>

            {/* Ezek a fájlok a TELJES diszpó levél mellékleteként mennek ki a
                stábnak (az előzetes diszpó egy rövid tájékoztató, ahhoz nem).
                A tárolás az R2-n van, a levélbe küldéskor mindig a legfrissebb
                változat kerül - lásd backend services/dispo.py. */}
            <Card title="Csatolni való (a diszpó levélhez)" icon={Paperclip}>
              <DokumentumFeltoltes
                entityType="project"
                entityId={projectId}
                attachments={attachments.filter((a) => a.kategoria === "diszpo")}
                kategoria="diszpo"
                canEdit={szerkeszthet}
                canDelete={torolhet}
                emptyText="Nincs csatolni való fájl - a diszpó a szokásos PDF-fel megy ki."
              />
            </Card>
          </>
        ),
      },
      {
        key: "szerzodes-tig",
        label: "Szerződés & TIG",
        content: (
          <>
            <Card title="Szerződés készítés" icon={Wallet}>
              <SubcontractorContractManager
                projectId={project.id}
                pending={pendingContracts?.pending ?? []}
                teljesitesAlap={pendingContracts?.teljesites_szoveg_alap ?? ""}
              />
              {/* A kiküldött szerződés eltűnik a fenti (teendő-)listáról -
                  itt látszik, kinek van kész papírja, és hol van. */}
              <ElkeszultSzerzodesek projectId={project.id} szerzodesek={osszesSzerzodes} />
            </Card>
            <Card title="Teljesítési igazolás (Külsős TIG)" icon={FileText}>
              {pendingTig?.tig_ready ? (
                <PerformanceCertificateManager
                  projectId={project.id}
                  pending={pendingTig.pending}
                  teljesitesAlap={pendingTig.teljesites_szoveg_alap}
                />
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
                canEdit={pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit")}
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
                <>
                  <VagasiKoltsegOsszesen
                    lezartPercek={lezartPercek}
                    lezartKoltseg={lezartKoltseg}
                    futok={futoMeresek}
                    showCost={lathatKoltseget}
                  />
                  {/* KI mennyit dolgozott a projekt anyagain - enélkül csak
                      egy összesített idő állt itt, és nem derült ki, kié. */}
                  {vagokBontasa.length > 0 && (
                    <div className="mb-4 space-y-1 border-b border-border pb-3">
                      {vagokBontasa.map((v) => (
                        <div key={v.employee_id} className="flex items-center justify-between text-[12.5px]">
                          <a href={`/csapat/${v.employee_id}`} className="text-text-secondary hover:underline">
                            {v.full_name}
                          </a>
                          <span className="tabular-nums text-text-secondary">
                            {formatPercek(v.total_minutes)}
                            {lathatKoltseget && v.total_cost != null && (
                              <span className="text-text-muted"> · {formatFt(v.total_cost)}</span>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
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
      <div className="flex-1 space-y-8 p-8">
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
                className="btn btn-danger"
              />
            </>
          }
        />

        <DetailSections sections={tabs} entityType="project" canReorder={szerepkorei(currentUser).includes("admin")} />
      </div>
    </div>
  );
}
