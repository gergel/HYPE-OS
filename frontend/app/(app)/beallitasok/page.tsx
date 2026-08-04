import { AccountCard } from "@/components/AccountCard";
import { CalendarSyncPanel } from "@/components/CalendarSyncPanel";
import { Card } from "@/components/Card";
import { DetailTabEditor } from "@/components/DetailTabEditor";
import { DispoResponsiblesManager } from "@/components/DispoResponsiblesManager";
import { EmployeeAccessManager } from "@/components/EmployeeAccessManager";
import { EntityFieldManager } from "@/components/EntityFieldManager";
import { NotionImportPanel } from "@/components/NotionImportPanel";
import { RevokeAllOthersButton } from "@/components/RevokeAllOthersButton";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getAllDetailTabs,
  getDispoResponsibles,
  getAllFieldVisibility,
  getAllPageAccess,
  getCurrentUser,
  getEmployees,
  getSampleRecord,
} from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";
import { EQUIPMENT_WIDGET_FIELD_KEY, FORGATAS_IDOPONT_WIDGET_FIELD_KEY } from "@/lib/detailTabs";
import { pagePermissionGroups } from "@/lib/nav";

/** A 8 entitás, aminek van generikus, fület-alapú részletnézete (lásd
 * app/*[id]/page.tsx, lib/detailTabs.tsx) - ehhez a 8-hoz kapcsolódik admin
 * fül-szerkesztő ÉS a Felhasználó-kezelésben megjelenő fülenkénti
 * Látja/Szerkesztheti jogosultság-választó. A page érték mindig a backend
 * build_crud_router page= paraméterével kell, hogy egyezzen. */
const ENTITY_PAGE_MAP: Record<string, string> = {
  project: "/projektek",
  client: "/ugyfelek",
  projectCode: "/projektek/project-kodok",
  employee: "/csapat",
  equipment: "/felszereles",
  campaign: "/kampanyok",
  task: "/feladatok",
  deliverable: "/utomunka",
};

/** A részletnézeteken szereplő entitások, ugyanazokkal a hide-listákkal, mint
 * a saját oldaluk (lásd app/*.tsx), hogy a mező-láthatóság beállítás
 * pontosan azokat a mezőket sorolja fel, amik ténylegesen megjeleníthetők. */
const VISIBILITY_ENTITIES: { entityType: string; label: string; basePath: string; hide: string[] }[] = [
  { entityType: "project", label: "Projektek", basePath: ENTITY_PATHS.project, hide: ["project_code_id", "campaign_id", "crew_employee_ids", "szerzodes_keszites_employee_id", "alvallakozo_keretszerzodes_contract_id"] },
  { entityType: "client", label: "Ügyfelek", basePath: ENTITY_PATHS.client, hide: [] },
  { entityType: "projectCode", label: "Project Code-ok", basePath: ENTITY_PATHS.projectCode, hide: ["client_id", "contract_id"] },
  { entityType: "employee", label: "Crew", basePath: ENTITY_PATHS.employee, hide: ["hashed_password"] },
  { entityType: "equipment", label: "Felszerelés", basePath: ENTITY_PATHS.equipment, hide: ["project_ids"] },
  { entityType: "campaign", label: "Kampányok", basePath: ENTITY_PATHS.campaign, hide: ["felelos_employee_id", "client_id"] },
  { entityType: "task", label: "Feladatok", basePath: ENTITY_PATHS.task, hide: [] },
  { entityType: "expense", label: "Kiadások", basePath: ENTITY_PATHS.expense, hide: ["project_code_id", "employee_id"] },
  { entityType: "revenue", label: "Bevételek", basePath: ENTITY_PATHS.revenue, hide: ["project_code_id"] },
  {
    entityType: "deliverable",
    label: "Utómunka",
    basePath: ENTITY_PATHS.deliverable,
    hide: [
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
    ],
  },
];

export default async function BeallitasokPage() {
  const [employees, pageAccessConfigs, fieldVisibilityConfigs, samples, currentUser, allDetailTabs, dispoResponsibles] =
    await Promise.all([
    getEmployees(),
    getAllPageAccess(),
    getAllFieldVisibility(),
    Promise.all(VISIBILITY_ENTITIES.map((e) => getSampleRecord(e.basePath))),
    getCurrentUser(),
    getAllDetailTabs(),
      getDispoResponsibles(),
    ]);
  const pages = pagePermissionGroups();

  const visibilityEntities = VISIBILITY_ENTITIES.map((entity, i) => {
    const sample = samples[i];
    if (!sample) return null;
    const availableFields = toEditableDetailFields(sample, entity.hide, null).map((f) => ({ key: f.key, label: f.label }));
    // A Projekt oldal eszközfoglaló widgetje nem valódi DB-mező, de a
    // felhasználó ugyanúgy tudja akarja fülre helyezni/munkatársanként
    // elrejteni, mint bármelyik mezőt - ezért szintetikus kulcsként
    // felvesszük ide, hogy megjelenjen a lenti mező-láthatóság checkbox-listán
    // ÉS a Részletnézet fülek szerkesztőjében is (lásd lib/detailTabs.tsx
    // buildFieldTabs widgets paramétere).
    if (entity.entityType === "project") {
      availableFields.push({ key: EQUIPMENT_WIDGET_FIELD_KEY, label: "Eszközök (widget)" });
      availableFields.push({ key: FORGATAS_IDOPONT_WIDGET_FIELD_KEY, label: "Forgatás időpontja (widget)" });
    }
    return {
      entityType: entity.entityType,
      label: entity.label,
      availableFields,
    };
  }).filter((e): e is { entityType: string; label: string; availableFields: { key: string; label: string }[] } => e !== null);

  const detailTabEntities = visibilityEntities.filter((e) => e.entityType in ENTITY_PAGE_MAP);
  const detailTabsByEntity = Object.fromEntries(allDetailTabs.map((c) => [c.entity_type, c.tabs]));
  const pageTabsMap = Object.fromEntries(
    Object.entries(ENTITY_PAGE_MAP).map(([entityType, page]) => [
      page,
      (detailTabsByEntity[entityType] ?? []).filter((t: { tab_key: string }) => t.tab_key !== "_other"),
    ]),
  );

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <AccountCard />

        <Card title="Felhasználó-kezelés">
          <p className="mb-3 text-[13px] text-text-secondary">
            Válaszd ki (kereséssel) a munkatársat, akinek be szeretnéd állítani a felhasználónevét (email), jelszavát, illetve hogy
            pontosan mely oldalakat és azokon belül mely mezőket lássa - csak admin szerkesztheti, az érintett munkatárs saját maga
            nem módosíthatja.
          </p>
          <EmployeeAccessManager
            employees={employees}
            pages={pages}
            visibilityEntities={visibilityEntities}
            pageAccessConfigs={pageAccessConfigs}
            fieldVisibilityConfigs={fieldVisibilityConfigs}
            pageTabsMap={pageTabsMap}
          />
        </Card>

        <Card title="Részletnézet fülek">
          <p className="mb-3 text-[13px] text-text-secondary">
            Az entitások részletnézetén megjelenő fülek elrendezése - mely mezők melyik fülbe kerüljenek, milyen sorrendben és
            néven/ikonnal. Amit egyik fül sem tartalmaz, az automatikusan az &quot;Egyéb&quot; fülre kerül a részletnézeten - nem vész el.
          </p>
          <DetailTabEditor entities={detailTabEntities} initialConfigsByEntity={detailTabsByEntity} />
        </Card>

        {currentUser?.role === "admin" && (
          <Card title="Mezők kezelése">
            <p className="mb-3 text-[13px] text-text-secondary">
              A Notionből áthozott mezők közül sok itt már nem kell - ezeket eltávolíthatod, és újakat is létrehozhatsz. Az
              eltávolított mező az EGÉSZ rendszerből eltűnik (adatlap, listák, szerkesztés); az &quot;Eltávolítás&quot; a benne
              tárolt adatot meghagyja, a kuka gomb véglegesen törli is. Bármikor visszahozható - ha az adatát is töröltük,
              üresen tér vissza. Ha csak EGY munkatárstól akarsz elrejteni egy mezőt, arra a lenti mező-láthatóság való.
            </p>
            <EntityFieldManager entities={visibilityEntities.map((e) => ({ entityType: e.entityType, label: e.label }))} />
          </Card>
        )}

        {currentUser?.role === "admin" && (
          <Card title="Notion import">
            <p className="mb-3 text-[13px] text-text-secondary">
              A teljes (mind a 3 kör) idempotens Notion import elindítása innen, a böngészőből - nincs szükség `railway ssh`-ra, a
              háttérben a Railway-en futó backend service saját processzében fut le, ezért egy megszakadt kapcsolat nem szakítja
              félbe.
            </p>
            <NotionImportPanel />
          </Card>
        )}

        {currentUser?.role === "admin" && (
          <Card title="Diszpó felelősök">
            <p className="mb-3 text-[13px] text-text-secondary">
              Akik itt szerepelnek, azoknak a &quot;Teendőim&quot; widget minden nap felhozza a MÁSNAPI forgatások
              diszpóit. A két oldal külön névsor, és külön feltétellel kerül le a teendő - egy ember mindkét oldalon
              szerepelhet.
            </p>
            <DispoResponsiblesManager initial={dispoResponsibles} employees={employees} />
          </Card>
        )}

        {currentUser?.role === "admin" && (
          <Card title="Naptár szinkron">
            <p className="mb-3 text-[13px] text-text-secondary">
              A HYPE CALENDAR nevű Google Naptárban létrehozott/módosított/törölt eseményeket percenként automatikusan
              tükrözi ide, Projektként (a naptárban törölt esemény a Projektet is törli, a szerkesztés felülírja a
              dátumot/helyszínt/nevet). Az újonnan érkező projektek egy közös &quot;Naptárból importált (rendezetlen)&quot;
              Project Code alá kerülnek, amíg admin át nem sorolja őket.
            </p>
            <CalendarSyncPanel />
          </Card>
        )}

        <Card title="Veszélyzóna">
          <p className="mb-3 text-[13px] text-text-secondary">
            Egy kattintással törölheted mindenki más hozzáférését (a sajátod kivételével) - a munkatárs-rekordok megmaradnak, csak
            a jelszavuk törlődik és a hozzáférésük áll vissza alapértelmezettre. Utána egyénenként újra beállíthatod, akinek kell.
          </p>
          <RevokeAllOthersButton />
        </Card>

        <Card title="Rendszer">
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            <div>
              <dt className="text-[12px] text-text-muted">API cím</dt>
              <dd className="mt-0.5 text-[13px] text-text-primary">{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}</dd>
            </div>
            <div>
              <dt className="text-[12px] text-text-muted">Adatforrás</dt>
              <dd className="mt-0.5 text-[13px] text-text-primary">Notion import (idempotens, egyenkénti mezőleképezéssel)</dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  );
}
