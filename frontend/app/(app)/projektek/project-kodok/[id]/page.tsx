import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { ClientContractManager } from "@/components/ClientContractManager";
import { DetailSections } from "@/components/DetailSections";
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import { EditableBooleanCell } from "@/components/EditableBooleanCell";
import { EditableTableCell } from "@/components/EditableTableCell";
import { RelatedTable } from "@/components/RelatedTable";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { DataTable } from "@/components/DataTable";
import { TopBar } from "@/components/TopBar";
import {
  Contract,
  ENTITY_PATHS,
  formatHuf,
  getAttachments,
  getCurrentUser,
  getDetailTabs,
  getEmployees,
  getFieldTypes,
  getMyPagePermissions,
  getPendingClientContracts,
  getRecord,
  getRelated,
  getVisibleFields,
  type JsonRecord,
} from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";
import { canDoAction } from "@/lib/permissions";
import { FileText, TrendingDown, TrendingUp, Wallet } from "lucide-react";

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

  const [client, contract, projects, expenses, revenues, deliverables, pendingClientContracts, visibleFields, fieldTypes, dbTabs, pagePermissions, currentUser, attachments, allEmployees] =
    await Promise.all([
      projectCode.client_id ? getRecord(ENTITY_PATHS.client, Number(projectCode.client_id)) : null,
      projectCode.contract_id ? getRecord(ENTITY_PATHS.contract, Number(projectCode.contract_id)) : null,
      getRelated(ENTITY_PATHS.project, { project_code_id: projectCodeId }),
      getRelated(ENTITY_PATHS.expense, { project_code_id: projectCodeId }),
      getRelated(ENTITY_PATHS.revenue, { project_code_id: projectCodeId }),
      getRelated(ENTITY_PATHS.deliverable, { project_code_id: projectCodeId }),
      getPendingClientContracts(),
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

  const pendingEntry = pendingClientContracts.find((p) => p.project_code_id === projectCodeId) ?? null;

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath: `${ENTITY_PATHS.projectCode}/${projectCode.id}`,
    record: projectCode,
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
    alwaysHidden: ["client_id", "contract_id"],
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

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <Card title="Megrendelői szerződés" icon={FileText}>
            <ClientContractManager
              projectCodeId={projectCodeId}
              existingContract={contract as unknown as Contract | null}
              existingKeretszerzodesId={pendingEntry?.existing_keretszerzodes_id ?? null}
            />
          </Card>
          <Card title="Megrendelői TIG" icon={FileText}>
            <div className="space-y-3 text-[13px]">
              <label className="flex items-center gap-2 text-text-primary">
                <EditableBooleanCell
                  patchPath={`${ENTITY_PATHS.projectCode}/${projectCodeId}`}
                  field="tig_kikuldve"
                  value={typeof projectCode.tig_kikuldve === "boolean" ? projectCode.tig_kikuldve : false}
                />
                Projekt teljesítése igazolva (TIG kiküldve)
              </label>
              <div className="flex items-center gap-2">
                <span className="text-text-secondary">Státusz:</span>
                <EditableTableCell
                  patchPath={`${ENTITY_PATHS.projectCode}/${projectCodeId}`}
                  field="tig_statusza"
                  value={typeof projectCode.tig_statusza === "string" ? projectCode.tig_statusza : null}
                  placeholder="Nincs megadva"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-text-secondary">TIG link:</span>
                <EditableTableCell
                  patchPath={`${ENTITY_PATHS.projectCode}/${projectCodeId}`}
                  field="tig_url"
                  value={typeof projectCode.tig_url === "string" ? projectCode.tig_url : null}
                  placeholder="Nincs link"
                />
              </div>
              <DokumentumFeltoltes
                entityType="projectCode"
                entityId={projectCodeId}
                attachments={attachments.filter((a) => a.kategoria === "tig")}
                kategoria="tig"
                canEdit={canEditFiles}
                canDelete={canDeleteFiles}
                emptyText="Nincs feltöltött (aláírt) TIG."
              />
            </div>
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
          <Card title="További dokumentumok" icon={FileText}>
            <DokumentumFeltoltes
              entityType="projectCode"
              entityId={projectCodeId}
              attachments={attachments.filter((a) => a.kategoria === "egyeb" || a.kategoria === "szerzodes")}
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
