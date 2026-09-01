import {
  Clapperboard,
  FileText,
  Paperclip,
  Send,
  Users,
  Wrench,
} from "lucide-react";
import { ActionButton } from "@/components/ActionButton";
import { DiszpoKuldesGombok } from "@/components/DiszpoKuldesGombok";
import { Card } from "@/components/Card";
import { DeleteButton } from "@/components/DeleteButton";
import { DetailHeader } from "@/components/DetailHeader";
import { DetailSections } from "@/components/DetailSections";
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import { GyartasKomment } from "@/components/GyartasKomment";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EquipmentBookingManager } from "@/components/EquipmentBookingManager";
import { ForgatasIdopontEditor } from "@/components/ForgatasIdopontEditor";
import { StabLinker } from "@/components/StabLinker";
import { ProjektPapirokEsKoltsegek } from "@/components/projekt/ProjektPapirokEsKoltsegek";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { RelatedTable } from "@/components/RelatedTable";
import { TechnikaCheckButton } from "@/components/TechnikaCheckButton";
import { DISZPO_MAX_BAJT, DISZPO_MERET_TANACS } from "@/lib/csatolmany";
import { canDoAction, szerepkorei } from "@/lib/permissions";
import { TopBar } from "@/components/TopBar";
import { VagasiKoltsegOsszesen, type FutoMeres } from "@/components/deliverable/VagasiKoltsegOsszesen";
import {
  ENTITY_PATHS,
  getAttachments,
  getCurrentUser,
  getDetailTabs,
  getEmployees,
  getEquipment,
  getFieldTypes,
  getMyPagePermissions,
  getAllContractsForProject,
  getAllTigForProject,
  getProjektkodBontas,
  getProjektSzamlazok,
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
  // A forrásonkénti tükör-mezők és a kézi zár belső segédadatok (lásd backend
  // models/project.py) - a generikus mezőrácsban semmi keresnivalójuk.
  "naptar_datum_vege",
  "notion_datum_vege",
  "forgatas_datum_kezzel_beallitva",
  "veg_datum",
  "project_code_id",
  "campaign_id",
  "crew_employee_ids",
  "szerzodes_keszites_employee_id",
  "alvallakozo_keretszerzodes_contract_id",
  // A gyártás komment saját dobozt kapott (több sor, kattintható linkek,
  // csatolt fájlok) - a mezőrácsban egysoros beviteli mező lenne belőle,
  // ami épp azt veszi el, amiért ez a mező van.
  "gyartas_komment",
  // "Nem diszponálandó (meeting)": ezt a NAPTÁR-SZINKRON állítja be magától a
  // lila (meeting/helyszínbejárás) eseményekre - lásd services/google_calendar.py.
  // Nem kézzel töltendő mező, viszont egyedüliként lakta a szintetikus "Egyéb"
  // kártyát, tehát egy egész doboz állt az adatlapon egyetlen, magától
  // beálló pipáért. A jelölés attól még él, csak nem foglal helyet.
  "nem_diszponalando",
];

const PAGE = "/projektek";
//: A Diszpó menüpont jogosultsági kulcsa (lásd lib/nav.ts).
const DISZPO_PAGE = "/naptar";

export async function ProjectDetailContent({
  projectId,
  embedded = false,
  csakDiszpoNezet = false,
}: {
  projectId: number;
  embedded?: boolean;
  /** A DISZPÓ felől nyílt meg (lásd ProjectDetailModal `nezet`). Ilyenkor a
   * papírozás és a költségek kimaradnak: a diszpós munkája a forgatás, a
   * stáb, a technika és a két küldés - a papírok hetekkel később, más kézben
   * készülnek. A Projektek listából ugyanez a projekt TELJESEN nyílik meg. */
  csakDiszpoNezet?: boolean;
}) {
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
    visibleFields,
    fieldTypes,
    dbTabs,
    pagePermissions,
    sectionOrder,
    currentUser,
    attachments,
    szamlazoNezet,
  ] = await Promise.all([
    project.project_code_id ? getRecord(ENTITY_PATHS.projectCode, Number(project.project_code_id)) : null,
    project.campaign_id ? getRecord(ENTITY_PATHS.campaign, Number(project.campaign_id)) : null,
    getRelated(ENTITY_PATHS.deliverable, { project_id: projectId }),
    getEquipment(),
    getEmployees(),
    getRelated(ENTITY_PATHS.assignment, { project_id: projectId }),
    getVisibleFields("project"),
    getFieldTypes("project"),
    getDetailTabs("project"),
    getMyPagePermissions(),
    getSectionOrder("project"),
    getCurrentUser(),
    getAttachments("project", projectId),
    getProjektSzamlazok(projectId),
  ]);

  // A PAPÍROK és a KÖLTSÉG csak a teljes nézethez kellenek: a diszpó felől
  // megnyitva ezek a kártyák meg sem jelennek, tehát a lekérésük is felesleges
  // lenne (a diszpós leggyakrabban egy felugró ablakban nyitja meg a
  // projektet, és ott minden fölös hívás látszik a betöltésen).
  const [szerzodesek, tigek, bontas] = csakDiszpoNezet
    ? [[], [], null]
    : await Promise.all([
        getAllContractsForProject(projectId),
        getAllTigForProject(projectId),
        project.project_code_id ? getProjektkodBontas(Number(project.project_code_id)) : null,
      ]);

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
  // KI SZÁMÍT BELSŐSNEK EZEN A FORGATÁSON? Nem a mai típusa dönt: a belsős
  // státusz időszakos, és a projektek visszamenőlegesek. Aki ma belsős, de a
  // forgatás idején még külsősként dolgozott, az ide KÜLSŐSKÉNT kerül - és a
  // rendszer is úgy kezeli (kérdezi a napidíját, kér tőle szerződést és
  // TIG-et). A választ a szerver adja, mert a belsős időszakok ott vannak:
  // a `valaszthato_emberek` pontosan azokat sorolja, akik AZON A NAPON nem
  // voltak belsősök (lásd backend project_szamlazok._lehet_szamlazo).
  const nemBelsosAkkor = new Set(
    (szamlazoNezet?.valaszthato_emberek ?? [])
      .map((f) => Number(f.szamlazo.replace(/^e/, "")))
      .filter((id) => Number.isFinite(id)),
  );
  const csoportja = (e: (typeof allEmployees)[number]) => {
    // A számlázó-nézet nélkül (hiba esetén) marad a mai típus - az a régi,
    // ismert viselkedés, nem egy rosszabb találgatás.
    if (!szamlazoNezet) return e.tipus;
    if (nemBelsosAkkor.has(e.id)) return e.tipus === "belsos" ? "kulsos" : e.tipus;
    return "belsos";
  };
  const crewOptions = allEmployees.map((e) => ({
    id: e.id,
    label: e.full_name,
    href: `/csapat/${e.id}`,
    sublabel: e.email,
    group: csoportja(e),
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
  // A szerződés/TIG kártyák (ProjektPapirokEsKoltsegek) az Utókövetés-
  // hozzáféréshez kötöttek - akinek ez nincs meg, annak a kártyák sem
  // jelennek meg, nem csak az összegek bennük.
  const lathatUtokovetest = pagePermissions === null || !!pagePermissions["/utokovetes"]?.includes("view");
  // A diszpó-mellékleteket az szerkesztheti, aki a Projekteket is - ugyanaz a
  // jog, amit a backend is ellenőriz (services/attachments.py ENTITAS_OLDALAK).
  //
  // A canDoAction az OLDAL-ALIASZOKAT is nézi: akinek csak DISZPÓ (naptár)
  // hozzáférése van, az itt is szerkeszthet, mert a diszpó munkája ezen az
  // oldalon van (lásd lib/permissions.OLDAL_ALIASZOK és a backend
  // core/security.OLDAL_ALIASZOK).
  const szerkeszthet = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  const torolhet = canDoAction(currentUser, pagePermissions, PAGE, "delete");

  // SZŰKÍTETT (diszpós) NÉZET - két okból lehet:
  //
  // 1. a DISZPÓ felől nyitották meg (csakDiszpoNezet): ott a projekt a
  //    diszponáláshoz kell - forgatás, stáb, technika, gyártás komment, a két
  //    küldés. A papírozás és a költségek hetekkel később, más kézben
  //    történnek, ide csak zajt vinnének. A Projektek listából ugyanez a
  //    projekt teljesen nyílik meg;
  // 2. a felhasználónak CSAK diszpó hozzáférése van: neki a papírozás
  //    úgyis 403 lenne, és egy működésképtelen kártya rosszabb, mint a hiánya.
  const csakDiszpo =
    csakDiszpoNezet || (pagePermissions !== null && !pagePermissions[PAGE] && !!pagePermissions[DISZPO_PAGE]);

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
      // A forgatás időpontja ugyanahhoz a joghoz kötött, mint a többi szekció -
      // az aliaszokkal együtt (a diszpósnak a forgatás időpontja is kell).
      [FORGATAS_IDOPONT_WIDGET_FIELD_KEY]: (
        <ForgatasIdopontEditor
          patchPath={patchPath}
          initial={{
            start: asText(project.forgatas_datuma),
            startTime: asText(project.forgatas_kezdes_ido).slice(0, 5),
            // A TÉNYLEGES záró nap: a naptárból/Notionből tükrözött vég is
            // automatikusan megjelenik itt (lásd backend
            // schemas/project.veg_datum) - pontosan, ahogy a felhasználó
            // kérte: ami több napos, annál a záró dátum magától ki van töltve.
            end: asText((project.veg_datum as string | null) ?? project.forgatas_datuma_vege),
            endTime: asText(project.forgatas_veg_ido).slice(0, 5),
          }}
          readOnly={!szerkeszthet}
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
              {/* Kliens-komponens: a sikeres küldés AZONNAL zöld "Kiküldve"
                  jelzésre és "Újraküldés" gombra vált, nem a szerver-frissítést
                  várja (a felhasználó kérése). */}
              <DiszpoKuldesGombok
                projectId={Number(project.id)}
                elozetesAllapot={elozetesAllapot}
                diszpoAllapot={diszpoAllapot}
              />
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
                maxOsszMeretBajt={DISZPO_MAX_BAJT}
                meretTanacs={DISZPO_MERET_TANACS}
              />
            </Card>

            {/* A gyártásvezető jegyzettömbje a projekten: szabad szöveg
                sortörésekkel és kattintható linkekkel, plusz a hozzá tartozó
                fájlok. Nem a mezőrácsban van, mert ott egysoros mező lenne -
                ide viszont bekezdések, felsorolások és Drive-linkek kerülnek. */}
            <Card title="Gyártás komment" icon={FileText}>
              <GyartasKomment
                projectId={projectId}
                patchPath={patchPath}
                ertek={asText(project.gyartas_komment)}
                attachments={attachments.filter((a) => a.kategoria === "gyartas")}
                canEdit={szerkeszthet}
                canDelete={torolhet}
              />
            </Card>
          </>
        ),
      },
      // A papírozás MŰVELETEI (generálás, kiküldés, aláírt példány, számla)
      // szándékosan nincsenek itt: azok hetekkel később, más kézben és EGYBEN
      // történnek - arra az Utókövetés oldal való, ahol az összes projektre
      // rálátva vannak (lásd app/(app)/utokovetes/[id]/page.tsx). Két helyen
      // ugyanaz a művelet csak azt eredményezte, hogy a diszpót író ember is
      // beleakadt.
      //
      // Az ÁLLÁSUK viszont az oldal alján látszik (lásd
      // ProjektPapirokEsKoltsegek): az adatlapot megnyitva a leggyakoribb
      // kérdés az, hogy megvan-e már minden ehhez a forgatáshoz, és mibe
      // került. A diszpó felől megnyitva az a blokk is kimarad.
      {
        key: "csapat",
        label: "Csapat & Utómunka",
        content: (
          <>
            <Card title={`Stáb (${crewIds.length})`} icon={Users}>
              {/* Nem sima M2mLinker: egy nem belsős stábtag felvétele után
                  rögtön megkérdezi, mennyiért vállalja azt a napot - a diszpó
                  írásakor ez dől el, a papírokat viszont hetekkel később más
                  készíti (lásd StabLinker). */}
              <StabLinker
                patchPath={patchPath}
                projectId={Number(project.id)}
                currentIds={crewIds}
                options={crewOptions}
                napSzoveg={asText(project.forgatas_datuma)}
                canEdit={szerkeszthet}
              />
            </Card>
            {!csakDiszpo && (
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
                // A projekt kódját ÖRÖKLI - projekthez felvezetett vágásnál nem
                // kell újra begépelni (a backend is ezt teszi, lásd
                // routes/postproduction._vagas_projektkodja).
                presetFields={{
                  project_id: project.id,
                  project_code_id: project.project_code_id,
                  projektkod_szoveg: project.projektkod_szoveg,
                }}
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
            )}
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
              {/* A papírozás (szerződés, TIG, kifizetés) nem ezen az oldalon
                  történik, hanem az Utókövetésben - ez a link vezet oda, hogy
                  ne kelljen keresgélni. */}
              <a
                href={`/utokovetes/${project.id}`}
                // Felugró ablakban (naptár/lista nézet) új lapon nyílik: az
                // iframe-en belül elnavigálva a modál keretében ragadna.
                target={embedded ? "_blank" : undefined}
                rel={embedded ? "noopener noreferrer" : undefined}
                className="text-text-accent hover:underline"
              >
                Szerződés &amp; TIG: Utókövetés
              </a>
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

        {/* PAPÍROK és KÖLTSÉG - áttekintésként, a mezők után. A diszpó felől
            megnyitva kimarad: ott a projekt a diszponáláshoz kell (lásd
            csakDiszpo). */}
        {!csakDiszpo && (
          <ProjektPapirokEsKoltsegek
            projectId={projectId}
            projectCodeId={project.project_code_id ? Number(project.project_code_id) : null}
            szerzodesek={szerzodesek}
            tigek={tigek}
            bontas={bontas}
            lathatKoltseget={lathatKoltseget}
            lathatUtokovetest={lathatUtokovetest}
          />
        )}
      </div>
    </div>
  );
}
