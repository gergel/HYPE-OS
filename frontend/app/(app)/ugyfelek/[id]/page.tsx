import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailSections } from "@/components/DetailSections";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { RelatedTable } from "@/components/RelatedTable";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getDetailTabs, getFieldTypes, getMyPagePermissions, getRecord, getRelated, getVisibleFields } from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";

const PAGE = "/ugyfelek";

export default async function UgyfelDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const clientId = Number(id);

  // Egyik lenti hívás sem függ az ügyfél rekord mezőitől, csak a clientId-tól
  // (ami az URL-ből már megvan) - a getRecord is ide kerül a saját külön
  // await helyett, egy kevesebb kör az oldalbetöltésnél.
  const [client, contacts, projectCodes, contracts, campaigns, visibleFields, fieldTypes, dbTabs, pagePermissions] =
    await Promise.all([
      getRecord(ENTITY_PATHS.client, clientId),
      getRelated(ENTITY_PATHS.contact, { client_id: clientId }),
      getRelated(ENTITY_PATHS.projectCode, { client_id: clientId }),
      getRelated(ENTITY_PATHS.contract, { client_id: clientId }),
      getRelated(ENTITY_PATHS.campaign, { client_id: clientId }),
      getVisibleFields("client"),
      getFieldTypes("client"),
      getDetailTabs("client"),
      getMyPagePermissions(),
    ]);
  if (!client) notFound();

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath: `${ENTITY_PATHS.client}/${client.id}`,
    record: client,
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <div className="space-y-2">
          <BackLink href="/ugyfelek" label="Ügyfelek" />
          <h1 className="t-page">{String(client.nev ?? `Ügyfél #${client.id}`)}</h1>
        </div>

        <DetailSections sections={tabs} />

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
          <RelatedTable
            rows={contacts}
            emptyText="Nincs kapcsolattartó ehhez az ügyfélhez."
            entityKey="contact"
            deleteBasePath={ENTITY_PATHS.contact}
          />
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
          <RelatedTable
            rows={contracts}
            emptyText="Nincs szerződés ehhez az ügyfélhez."
            getHref={(c) => `/szerzodesek/${c.id}`}
            deleteBasePath={ENTITY_PATHS.contract}
          />
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
