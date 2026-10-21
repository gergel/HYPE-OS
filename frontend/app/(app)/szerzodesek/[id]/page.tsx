import { notFound } from "next/navigation";
import { FileText } from "lucide-react";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
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
    // A dokumentum-URL/tárhelykulcs mezők nyers linkként zavaróak voltak a
    // mezőrácsban - ugyanezek a dokumentumok fent, a "Szerződés dokumentumai"
    // blokkban jelennek meg, felismerhető fájl-sorként.
    alwaysHidden: [
      "employee_id",
      "client_id",
      "project_id",
      "szerzodes_file_url",
      "szerzodes_file_storage_key",
      "alairt_file_url",
      "alairt_file_storage_key",
    ],
  });

  const title = String(contract.megbizas_targya || contract.nev || contract.ceg_neve || `Szerződés #${contract.id}`);

  // A MEZŐKBEN tárolt dokumentumok (generált/Notion-örökség) - a csatolmányok
  // mellett ezek is a fájlblokkban jelennek meg, hogy a rekordon látható
  // linkek és a blokk ne mondhassanak ellent egymásnak (962-es hibajelzés).
  const keret = contract.keretszerzodes === true;
  const oroklottDokumentumok = [
    ...(contract.szerzodes_file_url
      ? [
          {
            cimke: keret ? "Keretszerződés dokumentuma" : "Elkészült szerződés",
            url: String(contract.szerzodes_file_url),
            tipus: "Szerződés",
          },
        ]
      : []),
    ...(contract.alairt_file_url
      ? [
          {
            cimke: "Aláírt példány",
            url: String(contract.alairt_file_url),
            tipus: "Szerződés",
            jelzes: { label: "Aláírva", tone: "success" as const },
          },
        ]
      : []),
  ];
  // Aláírás állapota a fájltól KÜLÖN: lehet aláírva fájl nélkül (a papír
  // máshol landolt), és lehet fájl kiküldve aláírás nélkül.
  const alairasJelzes = contract.alairva
    ? { label: "Aláírva", tone: "success" as const }
    : { label: "Aláírásra vár", tone: "warning" as const };

  // A visszalépés célja a szerződés TÍPUSÁT követi - a nem keretszerződés
  // rekord korábban is "Keretszerződések"-re mutatott vissza (hibajelzés).
  const vissza = keret
    ? { href: "/penzugyek/keretszerzodesek", label: "Keretszerződések" }
    : { href: "/penzugyek/eseti-szerzodesek", label: "Eseti szerződések" };

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <div className="space-y-2">
          <BackLink href={vissza.href} label={vissza.label} />
          <h1 className="t-page">{title}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge label={keret ? "Keretszerződés" : "Eseti megbízási szerződés"} tone="neutral" />
            <StatusBadge label={alairasJelzes.label} tone={alairasJelzes.tone} />
          </div>
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
            oroklott={oroklottDokumentumok}
            kategoria="szerzodes"
            canEdit={canDoAction(currentUser, pagePermissions, PAGE, "edit")}
            canDelete={canDoAction(currentUser, pagePermissions, PAGE, "delete")}
            emptyText="Ehhez a szerződéshez nincs dokumentum - se csatolmány, se mezőben tárolt fájl."
          />
        </Card>

        <DetailSections sections={tabs} entityType="contract" />
      </div>
    </div>
  );
}
