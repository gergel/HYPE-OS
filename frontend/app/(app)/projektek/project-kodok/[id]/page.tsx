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
import { TopBar } from "@/components/TopBar";
import {
  Contract,
  ENTITY_PATHS,
  formatHuf,
  getAttachments,
  getCurrentUser,
  getDetailTabs,
  getFieldTypes,
  getMyPagePermissions,
  getPendingClientContracts,
  getRecord,
  getRelated,
  getVisibleFields,
} from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";
import { canDoAction } from "@/lib/permissions";
import { FileText, TrendingDown, TrendingUp, Wallet } from "lucide-react";

const PAGE = "/projektek/project-kodok";

export default async function ProjectCodeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectCodeId = Number(id);
  const projectCode = await getRecord(ENTITY_PATHS.projectCode, projectCodeId);
  if (!projectCode) notFound();

  const [client, contract, projects, expenses, revenues, deliverables, pendingClientContracts, visibleFields, fieldTypes, dbTabs, pagePermissions, currentUser, attachments] =
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
    ]);

  const canEditFiles = canDoAction(currentUser?.role, pagePermissions, PAGE, "edit");
  const canDeleteFiles = canDoAction(currentUser?.role, pagePermissions, PAGE, "delete");

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

        <Card title={`Kiadások (${expenses.length})`}>
          <RelatedTable
            rows={expenses}
            emptyText="Nincs kiadás ehhez a Project Code-hoz."
            getHref={(e) => `/penzugyek/kiadas/${e.id}`}
            deleteBasePath={ENTITY_PATHS.expense}
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
