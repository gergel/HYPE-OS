import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailSections } from "@/components/DetailSections";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getDetailTabs, getFieldTypes, getMyPagePermissions, getRecord, getRelated, getVisibleFields } from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";

const PAGE = "/projektek/project-kodok";

export default async function ProjectCodeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectCodeId = Number(id);
  const projectCode = await getRecord(ENTITY_PATHS.projectCode, projectCodeId);
  if (!projectCode) notFound();

  const [client, contract, projects, expenses, revenues, deliverables, visibleFields, fieldTypes, dbTabs, pagePermissions] =
    await Promise.all([
      projectCode.client_id ? getRecord(ENTITY_PATHS.client, Number(projectCode.client_id)) : null,
      projectCode.contract_id ? getRecord(ENTITY_PATHS.contract, Number(projectCode.contract_id)) : null,
      getRelated(ENTITY_PATHS.project, { project_code_id: projectCodeId }),
      getRelated(ENTITY_PATHS.expense, { project_code_id: projectCodeId }),
      getRelated(ENTITY_PATHS.revenue, { project_code_id: projectCodeId }),
      getRelated(ENTITY_PATHS.deliverable, { project_code_id: projectCodeId }),
      getVisibleFields("projectCode"),
      getFieldTypes("projectCode"),
      getDetailTabs("projectCode"),
      getMyPagePermissions(),
    ]);

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
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/projektek/project-kodok" label="Project Code-ok" />
        <h1 className="text-lg font-medium text-text-primary">
          {String(projectCode.projektkod ?? `Project Code #${projectCode.id}`)}
        </h1>
        <div className="flex flex-wrap gap-4 text-[13px] text-text-secondary">
          {client && (
            <a href={`/ugyfelek/${client.id}`} className="text-text-accent hover:underline">
              Ügyfél: {String(client.nev)}
            </a>
          )}
          {contract && <span>Szerződés: #{contract.id}</span>}
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
