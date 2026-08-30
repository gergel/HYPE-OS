import { notFound } from "next/navigation";
import { FileText } from "lucide-react";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailSections } from "@/components/DetailSections";
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getAttachments,
  getCurrentUser,
  getDetailTabs,
  getFieldTypes,
  getMyPagePermissions,
  getRecord,
  getSectionOrder,
  getVisibleFields,
} from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";
import { canDoAction } from "@/lib/permissions";

// A szerződéseknek eddig NEM volt részletnézetük: a kapcsolódó listákban (pl.
// egy Külsős "Szerződések" kártyáján) csak sorok voltak, kattintható cél
// nélkül - így bele sem lehetett nézni egy szerződésbe anélkül, hogy a
// Pénzügyek/Keretszerződések oldalon vadásszuk meg. Ez az oldal adja meg azt a
// célt, amire a kapcsolódó táblák (és a felugró ablak) hivatkozhatnak.
const PAGE = "/penzugyek";

export default async function ContractDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const contractId = Number(id);

  // Az employee/client/project a szerződés mezőitől függ (kikre mutat) - a
  // többi csak contractId-t vagy semmit nem kér, ezért azok a getRecord-dal
  // EGYSZERRE indulnak, nem utána: egy kevesebb kör az oldalbetöltésnél.
  const [contract, visibleFields, fieldTypes, dbTabs, pagePermissions, sectionOrder, currentUser, attachments] =
    await Promise.all([
      getRecord(ENTITY_PATHS.contract, contractId),
      getVisibleFields("contract"),
      getFieldTypes("contract"),
      getDetailTabs("contract"),
      getMyPagePermissions(),
      getSectionOrder("contract"),
      getCurrentUser(),
      getAttachments("contract", contractId),
    ]);
  if (!contract) notFound();

  const [employee, client, project] = await Promise.all([
    contract.employee_id ? getRecord(ENTITY_PATHS.employee, Number(contract.employee_id)) : null,
    contract.client_id ? getRecord(ENTITY_PATHS.client, Number(contract.client_id)) : null,
    contract.project_id ? getRecord(ENTITY_PATHS.project, Number(contract.project_id)) : null,
  ]);

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath: `${ENTITY_PATHS.contract}/${contract.id}`,
    record: contract,
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
    sectionOrder,
    alwaysHidden: ["employee_id", "client_id", "project_id"],
  });

  const title = String(contract.megbizas_targya || contract.nev || contract.ceg_neve || `Szerződés #${contract.id}`);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <div className="space-y-2">
          <BackLink href="/penzugyek/keretszerzodesek" label="Keretszerződések" />
          <h1 className="t-page">{title}</h1>
        </div>
        <div className="flex flex-wrap gap-4 text-[13px] text-text-secondary">
          {employee && (
            <a href={`/csapat/${employee.id}`} className="text-text-accent hover:underline">
              Munkatárs: {String(employee.full_name)}
            </a>
          )}
          {client && (
            <a href={`/ugyfelek/${client.id}`} className="text-text-accent hover:underline">
              Ügyfél: {String(client.nev)}
            </a>
          )}
          {project && (
            <a href={`/projektek/${project.id}`} className="text-text-accent hover:underline">
              Projekt: {String(project.nev)}
            </a>
          )}
        </div>

        <Card title="Szerződés dokumentumai" icon={FileText}>
          <DokumentumFeltoltes
            entityType="contract"
            entityId={contractId}
            attachments={attachments}
            kategoria="szerzodes"
            canEdit={canDoAction(currentUser, pagePermissions, PAGE, "edit")}
            canDelete={canDoAction(currentUser, pagePermissions, PAGE, "delete")}
            emptyText="Nincs feltöltött szerződés-fájl."
          />
        </Card>

        <DetailSections sections={tabs} entityType="contract" />
      </div>
    </div>
  );
}
