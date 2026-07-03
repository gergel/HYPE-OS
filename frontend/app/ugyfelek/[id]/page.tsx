import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailGrid } from "@/components/DetailGrid";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getRecord, getRelated } from "@/lib/api";
import { toDetailFields } from "@/lib/detail";

export default async function UgyfelDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const clientId = Number(id);
  const client = await getRecord(ENTITY_PATHS.client, clientId);
  if (!client) notFound();

  const [contacts, projectCodes, contracts, campaigns] = await Promise.all([
    getRelated(ENTITY_PATHS.contact, { client_id: clientId }),
    getRelated(ENTITY_PATHS.projectCode, { client_id: clientId }),
    getRelated(ENTITY_PATHS.contract, { client_id: clientId }),
    getRelated(ENTITY_PATHS.campaign, { client_id: clientId }),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/ugyfelek" label="Ügyfelek" />

        <Card title={String(client.nev ?? `Ügyfél #${client.id}`)}>
          <DetailGrid fields={toDetailFields(client)} />
        </Card>

        <Card title={`Kapcsolattartók (${contacts.length})`}>
          <RelatedTable rows={contacts} emptyText="Nincs kapcsolattartó ehhez az ügyfélhez." />
        </Card>

        <Card title={`Project Code-ok (${projectCodes.length})`}>
          <RelatedTable
            rows={projectCodes}
            emptyText="Nincs Project Code ehhez az ügyfélhez."
            getHref={(pc) => `/projektek/project-kodok/${pc.id}`}
          />
        </Card>

        <Card title={`Szerződések (${contracts.length})`}>
          <RelatedTable rows={contracts} emptyText="Nincs szerződés ehhez az ügyfélhez." />
        </Card>

        <Card title={`Kampányok (${campaigns.length})`}>
          <RelatedTable rows={campaigns} emptyText="Nincs kampány ehhez az ügyfélhez." getHref={(c) => `/kampanyok/${c.id}`} />
        </Card>
      </div>
    </div>
  );
}
