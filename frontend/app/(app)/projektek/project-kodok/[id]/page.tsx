import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailSections } from "@/components/DetailSections";
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import { MegrendeloiPapirKezelo } from "@/components/megrendeloi/MegrendeloiPapirKezelo";
import { PapirKapcsolok } from "@/components/megrendeloi/PapirKapcsolok";
import { RelatedTable } from "@/components/RelatedTable";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { DataTable } from "@/components/DataTable";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  formatHuf,
  getAttachments,
  getCurrentUser,
  getDetailTabs,
  getEmployees,
  getFieldTypes,
  getMegrendeloiKeretek,
  getMegrendeloiKontaktok,
  getMegrendeloiPapirok,
  getMyPagePermissions,
  getRecord,
  getRelated,
  getVisibleFields,
  type JsonRecord,
} from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";
import { canDoAction } from "@/lib/permissions";
import { FileCheck2, FileSignature, FileText, TrendingDown, TrendingUp, Wallet } from "lucide-react";

const PAGE = "/projektek/project-kodok";

/** MELYIK NAP ment ki a pénz.
 *
 * A Kiadásnak három dátuma lehet, és nem mindegyik van kitöltve: a
 * `fizetes_datuma` a tényleges kifizetés napja (ez a kérdés), a
 * `kiadas_datuma` a költség felmerülése, a `fizetes_hatarideje` pedig csak
 * terv. Ebben a sorrendben esünk vissza, hogy a régi, importált soroknál se
 * maradjon üres az oszlop - ott gyakran csak az utóbbi kettő van meg. */
function kiadasNapja(e: JsonRecord): string {
  for (const kulcs of ["fizetes_datuma", "kiadas_datuma", "fizetes_hatarideje"]) {
    const ertek = e[kulcs];
    if (typeof ertek === "string" && ertek) return ertek.slice(0, 10);
  }
  return "–";
}

/** KINEK fizettünk. A kiadás vagy egy munkatárshoz kötődik (túlóra, napidíj),
 * vagy dologi költség (benzin, parkolás) - utóbbinál nincs címzett. */
function kiadasCimzettje(e: JsonRecord, nevek: Map<number, string>): string {
  const id = typeof e.employee_id === "number" ? e.employee_id : null;
  if (id === null) return "–";
  return nevek.get(id) ?? `#${id}`;
}

export default async function ProjectCodeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectCodeId = Number(id);
  const projectCode = await getRecord(ENTITY_PATHS.projectCode, projectCodeId);
  if (!projectCode) notFound();

  const [
    client,
    contract,
    projects,
    expenses,
    revenues,
    deliverables,
    megrendeloiSzerzodesek,
    megrendeloiTigek,
    megrendeloiKeretek,
    megrendeloiKontaktok,
    visibleFields,
    fieldTypes,
    dbTabs,
    pagePermissions,
    currentUser,
    attachments,
    allEmployees,
  ] = await Promise.all([
    projectCode.client_id ? getRecord(ENTITY_PATHS.client, Number(projectCode.client_id)) : null,
    projectCode.contract_id ? getRecord(ENTITY_PATHS.contract, Number(projectCode.contract_id)) : null,
    getRelated(ENTITY_PATHS.project, { project_code_id: projectCodeId }),
    getRelated(ENTITY_PATHS.expense, { project_code_id: projectCodeId }),
    getRelated(ENTITY_PATHS.revenue, { project_code_id: projectCodeId }),
    getRelated(ENTITY_PATHS.deliverable, { project_code_id: projectCodeId }),
    // A megrendelői papírok (lásd backend routes/megrendeloi_papirok.py): a
    // szerződő fél a keretszerződésekből vagy a megrendelői kontaktokból
    // választható, ezért mindkét lista kell a szerkesztőhöz.
    getMegrendeloiPapirok("szerzodes", projectCodeId),
    getMegrendeloiPapirok("tig", projectCodeId),
    getMegrendeloiKeretek(),
    getMegrendeloiKontaktok(),
    getVisibleFields("projectCode"),
    getFieldTypes("projectCode"),
    getDetailTabs("projectCode"),
    getMyPagePermissions(),
    getCurrentUser(),
    getAttachments("projectCode", projectCodeId),
    // A kiadásoknál csak employee_id van, a táblában viszont nevet kell mutatni.
    getEmployees(),
  ]);

  const employeeNameById = new Map(allEmployees.map((e) => [e.id, e.full_name]));

  const canEditFiles = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  const canDeleteFiles = canDoAction(currentUser, pagePermissions, PAGE, "delete");

  // A papírozás kapcsolói (lásd backend models/project_code.py): a régi,
  // migráció előtti sorokon még hiányozhatnak, ezért az alapértéket itt is
  // ugyanúgy vesszük fel, ahogy a modell teszi.
  const vanSzerzodes = projectCode.van_szerzodes !== false;
  const papirNelkul = projectCode.papir_nelkul === true;
  const kellPapir = vanSzerzodes && !papirNelkul;

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath: `${ENTITY_PATHS.projectCode}/${projectCode.id}`,
    record: projectCode,
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
    // A papírozás kapcsolóinak SAJÁT kártyájuk van (lásd PapirKapcsolok): a
    // generikus mezőrácsban megjelenve nemcsak kétszer látszanának, hanem a
    // "papír nélkül" jelölés az indokot kérő ablakot is megkerülné - a
    // backend ugyan így is visszadobná, de hibaüzenettel, nem kérdéssel.
    alwaysHidden: ["client_id", "contract_id", "van_szerzodes", "papir_nelkul", "papir_nelkul_indoka"],
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-8">
        <div className="space-y-2">
          <BackLink href="/projektek/project-kodok" label="Project Code-ok" />
          <h1 className="t-page">
          {String(projectCode.projektkod ?? `Project Code #${projectCode.id}`)}
          </h1>
        </div>
        <div className="flex flex-wrap gap-4 text-[13px] text-text-secondary">
          {client && (
            <a href={`/ugyfelek/${client.id}`} className="text-text-accent hover:underline">
              Ügyfél: {String(client.nev)}
            </a>
          )}
          {contract && <span>Szerződés: #{contract.id}</span>}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="Összes költség (kiadások + utómunka)"
            value={formatHuf(typeof projectCode.osszes_koltseg === "number" ? projectCode.osszes_koltseg : 0)}
            icon={TrendingDown}
            tone="orange"
          />
          <StatCard
            label="Bevétel"
            value={formatHuf(revenues.reduce((sum, r) => sum + (typeof r.brutto === "number" ? r.brutto : 0), 0))}
            icon={TrendingUp}
            tone="teal"
          />
          <StatCard
            label="Becsült profit"
            value={formatHuf(typeof projectCode.becsult_profit === "number" ? projectCode.becsult_profit : 0)}
            icon={Wallet}
            tone={typeof projectCode.becsult_profit === "number" && projectCode.becsult_profit >= 0 ? "accent" : "danger"}
          />
        </div>

        {/* A papírozás onnan indul, hogy KELL-E egyáltalán papír - ezért van
            ez a kártya a két papír FÖLÖTT, nem valahol a mezők között. */}
        <Card title="Papírozás" icon={FileSignature}>
          <PapirKapcsolok
            patchPath={`${ENTITY_PATHS.projectCode}/${projectCodeId}`}
            vanSzerzodes={vanSzerzodes}
            papirNelkul={papirNelkul}
            papirNelkulIndoka={typeof projectCode.papir_nelkul_indoka === "string" ? projectCode.papir_nelkul_indoka : null}
            canEdit={canEditFiles}
          />
        </Card>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card title="Megrendelői szerződés" icon={FileText}>
            <MegrendeloiPapirKezelo
              projectCodeId={projectCodeId}
              fajta="szerzodes"
              papirok={megrendeloiSzerzodesek}
              keretek={megrendeloiKeretek}
              kontaktok={megrendeloiKontaktok}
              canEdit={canEditFiles}
              kellPapir={kellPapir}
            />
          </Card>
          <Card title="Megrendelői TIG" icon={FileCheck2}>
            <MegrendeloiPapirKezelo
              projectCodeId={projectCodeId}
              fajta="tig"
              papirok={megrendeloiTigek}
              keretek={megrendeloiKeretek}
              kontaktok={megrendeloiKontaktok}
              canEdit={canEditFiles}
              kellPapir={kellPapir}
            />
          </Card>
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card title="Megrendelői számlák" icon={FileText}>
            <DokumentumFeltoltes
              entityType="projectCode"
              entityId={projectCodeId}
              attachments={attachments.filter((a) => a.kategoria === "szamla")}
              kategoria="szamla"
              canEdit={canEditFiles}
              canDelete={canDeleteFiles}
              emptyText="Nincs feltöltött számla."
            />
          </Card>
          {/* A "tig"/"szerzodes" kategóriájú régi feltöltések is itt maradnak
              elérhetők: a papírok saját fájljai már a fenti kezelőkben vannak,
              de a rendszer előtti, kézzel feltöltött példányok nem tűnhetnek el. */}
          <Card title="További dokumentumok" icon={FileText}>
            <DokumentumFeltoltes
              entityType="projectCode"
              entityId={projectCodeId}
              attachments={attachments.filter(
                (a) => a.kategoria === "egyeb" || a.kategoria === "szerzodes" || a.kategoria === "tig",
              )}
              kategoria="egyeb"
              canEdit={canEditFiles}
              canDelete={canDeleteFiles}
            />
          </Card>
        </div>

        <DetailSections sections={tabs} />

        <Card title={`Projektek (${projects.length})`}>
          <RelatedTable
            rows={projects}
            emptyText="Nincs projekt ehhez a Project Code-hoz."
            getHref={(p) => `/projektek/${p.id}`}
            deleteBasePath={ENTITY_PATHS.project}
          />
        </Card>

        {/* A kiadásoknál a generikus kapcsolt-tábla (RelatedTable) használhatatlan
            volt: az "Állapot" és a "Dátum" oszlopa végig üres maradt, mert a
            Kiadás nem `allapot`/`datum` néven tárolja ezeket. Itt az a kérdés,
            hogy MELYIK NAP, KINEK és MENNYIT fizettünk ki - ezért saját tábla. */}
        <Card title={`Kiadások (${expenses.length})`}>
          <DataTable<JsonRecord>
            rows={expenses}
            emptyText="Nincs kiadás ehhez a Project Code-hoz."
            getHref={(e) => `/penzugyek/kiadas/${e.id}`}
            deleteHref={canDeleteFiles ? (e) => `${ENTITY_PATHS.expense}/${e.id}` : undefined}
            filterable
            columns={[
              {
                header: "Dátum",
                render: (e) => kiadasNapja(e),
                sortAccessor: (e) => kiadasNapja(e),
              },
              {
                header: "Kinek",
                render: (e) => kiadasCimzettje(e, employeeNameById),
                sortAccessor: (e) => kiadasCimzettje(e, employeeNameById),
              },
              {
                header: "Megnevezés",
                render: (e) => (typeof e.megnevezes === "string" ? e.megnevezes : "–"),
                sortAccessor: (e) => (typeof e.megnevezes === "string" ? e.megnevezes : ""),
              },
              {
                header: "Nettó",
                align: "right",
                render: (e) => formatHuf(typeof e.netto === "number" ? e.netto : null),
                sortAccessor: (e) => (typeof e.netto === "number" ? e.netto : 0),
              },
              {
                header: "Bruttó",
                align: "right",
                render: (e) => formatHuf(typeof e.brutto === "number" ? e.brutto : null),
                sortAccessor: (e) => (typeof e.brutto === "number" ? e.brutto : 0),
              },
              {
                header: "Állapot",
                align: "right",
                render: (e) => <StatusBadge label={e.kesz ? "Kifizetve" : "Nyitott"} tone={e.kesz ? "success" : "warning"} />,
                sortAccessor: (e) => (e.kesz ? 1 : 0),
              },
            ]}
          />
        </Card>

        <Card title={`Bevételek (${revenues.length})`}>
          <RelatedTable
            rows={revenues}
            emptyText="Nincs bevétel ehhez a Project Code-hoz."
            getHref={(r) => `/penzugyek/bevetel/${r.id}`}
            deleteBasePath={ENTITY_PATHS.revenue}
          />
        </Card>

        <Card title={`Utómunka (${deliverables.length})`}>
          <RelatedTable
            rows={deliverables}
            emptyText="Nincs vágandó anyag ehhez a Project Code-hoz."
            getHref={(d) => `/utomunka/${d.id}`}
            deleteBasePath={ENTITY_PATHS.deliverable}
          />
        </Card>
      </div>
    </div>
  );
}
