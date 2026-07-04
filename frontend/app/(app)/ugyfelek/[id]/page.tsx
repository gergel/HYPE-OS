import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getFieldTypes, getRecord, getRelated, getVisibleFields } from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";

export default async function UgyfelDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const clientId = Number(id);
  const client = await getRecord(ENTITY_PATHS.client, clientId);
  if (!client) notFound();

  const [contacts, projectCodes, contracts, campaigns, visibleFields, fieldTypes] = await Promise.all([
    getRelated(ENTITY_PATHS.contact, { client_id: clientId }),
    getRelated(ENTITY_PATHS.projectCode, { client_id: clientId }),
    getRelated(ENTITY_PATHS.contract, { client_id: clientId }),
    getRelated(ENTITY_PATHS.campaign, { client_id: clientId }),
    getVisibleFields("client"),
    getFieldTypes("client"),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/ugyfelek" label="Ügyfelek" />

        <Card title={String(client.nev ?? `Ügyfél #${client.id}`)}>
          <EditableDetailGrid
            patchPath={`${ENTITY_PATHS.client}/${client.id}`}
            fields={toEditableDetailFields(client, [], visibleFields, fieldTypes)}
          />
        </Card>

        <Card title={`Kapcsolattartók (${contacts.length})`}>
          <QuickCreateForm
            postPath={ENTITY_PATHS.contact}
            addLabel="+ Új kapcsolattartó hozzáadása"
            presetFields={{ client_id: client.id }}
            fields={[
              { name: "full_name", label: "Név", required: true },
              { name: "email", label: "Email" },
              { name: "phone", label: "Telefon" },
            ]}
          />
          <RelatedTable rows={contacts} emptyText="Nincs kapcsolattartó ehhez az ügyfélhez." deleteBasePath={ENTITY_PATHS.contact} />
        </Card>

        <Card title={`Project Code-ok (${projectCodes.length})`}>
          <RelatedTable
            rows={projectCodes}
            emptyText="Nincs Project Code ehhez az ügyfélhez."
            getHref={(pc) => `/projektek/project-kodok/${pc.id}`}
            deleteBasePath={ENTITY_PATHS.projectCode}
          />
        </Card>

        <Card title={`Szerződések (${contracts.length})`}>
          <RelatedTable rows={contracts} emptyText="Nincs szerződés ehhez az ügyfélhez." deleteBasePath={ENTITY_PATHS.contract} />
        </Card>

        <Card title={`Kampányok (${campaigns.length})`}>
          <RelatedTable
            rows={campaigns}
            emptyText="Nincs kampány ehhez az ügyfélhez."
            getHref={(c) => `/kampanyok/${c.id}`}
            deleteBasePath={ENTITY_PATHS.campaign}
          />
        </Card>
      </div>
    </div>
  );
}
