import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getFieldTypes, getRecord, getRelated, getVisibleFields } from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";

export default async function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const campaignId = Number(id);
  const campaign = await getRecord(ENTITY_PATHS.campaign, campaignId);
  if (!campaign) notFound();

  const [felelos, client, projects, deliverables, visibleFields, fieldTypes] = await Promise.all([
    campaign.felelos_employee_id ? getRecord(ENTITY_PATHS.employee, Number(campaign.felelos_employee_id)) : null,
    campaign.client_id ? getRecord(ENTITY_PATHS.client, Number(campaign.client_id)) : null,
    getRelated(ENTITY_PATHS.project, { campaign_id: campaignId }),
    getRelated(ENTITY_PATHS.deliverable, { campaign_id: campaignId }),
    getVisibleFields("campaign"),
    getFieldTypes("campaign"),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/kampanyok" label="Kampányok" />

        <Card title={String(campaign.nev ?? `Kampány #${campaign.id}`)}>
          <div className="mb-4 flex flex-wrap gap-4 text-[13px] text-text-secondary">
            {felelos && (
              <a href={`/csapat/${felelos.id}`} className="text-text-accent hover:underline">
                Felelős: {String(felelos.full_name)}
              </a>
            )}
            {client && (
              <a href={`/ugyfelek/${client.id}`} className="text-text-accent hover:underline">
                Ügyfél: {String(client.nev)}
              </a>
            )}
          </div>
          <EditableDetailGrid
            patchPath={`${ENTITY_PATHS.campaign}/${campaign.id}`}
            fields={toEditableDetailFields(campaign, ["felelos_employee_id", "client_id"], visibleFields, fieldTypes)}
          />
        </Card>

        <Card title={`Projektek (${projects.length})`}>
          <RelatedTable
            rows={projects}
            emptyText="Nincs projekt ehhez a kampányhoz."
            getHref={(p) => `/projektek/${p.id}`}
            deleteBasePath={ENTITY_PATHS.project}
          />
        </Card>

        <Card title={`Utómunka (${deliverables.length})`}>
          <RelatedTable
            rows={deliverables}
            emptyText="Nincs vágandó anyag ehhez a kampányhoz."
            getHref={(d) => `/utomunka/${d.id}`}
            deleteBasePath={ENTITY_PATHS.deliverable}
          />
        </Card>
      </div>
    </div>
  );
}
