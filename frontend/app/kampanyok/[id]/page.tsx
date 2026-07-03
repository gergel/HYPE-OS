import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailGrid } from "@/components/DetailGrid";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getRecord, getRelated } from "@/lib/api";
import { toDetailFields } from "@/lib/detail";

export default async function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const campaignId = Number(id);
  const campaign = await getRecord(ENTITY_PATHS.campaign, campaignId);
  if (!campaign) notFound();

  const [felelos, client, projects, deliverables] = await Promise.all([
    campaign.felelos_employee_id ? getRecord(ENTITY_PATHS.employee, Number(campaign.felelos_employee_id)) : null,
    campaign.client_id ? getRecord(ENTITY_PATHS.client, Number(campaign.client_id)) : null,
    getRelated(ENTITY_PATHS.project, { campaign_id: campaignId }),
    getRelated(ENTITY_PATHS.deliverable, { campaign_id: campaignId }),
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
          <DetailGrid fields={toDetailFields(campaign, ["felelos_employee_id", "client_id"])} />
        </Card>

        <Card title={`Projektek (${projects.length})`}>
          <RelatedTable rows={projects} emptyText="Nincs projekt ehhez a kampányhoz." getHref={(p) => `/projektek/${p.id}`} />
        </Card>

        <Card title={`Utómunka (${deliverables.length})`}>
          <RelatedTable rows={deliverables} emptyText="Nincs vágandó anyag ehhez a kampányhoz." getHref={(d) => `/utomunka/${d.id}`} />
        </Card>
      </div>
    </div>
  );
}
