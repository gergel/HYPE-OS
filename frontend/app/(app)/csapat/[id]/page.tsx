import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { BelsosTigEmployeeList } from "@/components/BelsosTigEmployeeList";
import { Card } from "@/components/Card";
import { CollapsibleCard } from "@/components/CollapsibleCard";
import { DetailSections } from "@/components/DetailSections";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { MunkaszerzodesUpload } from "@/components/MunkaszerzodesUpload";
import { RelatedTable } from "@/components/RelatedTable";
import { UtomunkaIdoHavonta } from "@/components/UtomunkaIdoHavonta";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getBelsosTigForEmployee,
  getDetailTabs,
  getEmployeeDocuments,
  getFieldTypes,
  getMyPagePermissions,
  getRecord,
  getRelated,
  getUtomunkaIdo,
  getVisibleFields,
} from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";
import { buildFieldTabs } from "@/lib/detailTabs";

/** Ezek az adatok másolódnak át előtöltésként az alvállalkozói eseti
 * szerződés generálásakor (lásd backend/app/api/routes/subcontractor_contracts.py
 * _get_or_create_draft) - ezért egy külön, jól látható szekcióban gyűjtjük
 * össze őket a crew tag oldalán, hogy egyszer kelljen csak kitölteni. */
const VALLALKOZAS_FIELD_KEYS = [
  "vallakozas_neve",
  "vallalkozas_kepviselo",
  "vallakozas_szekhely",
  "vallalkozas_adoszama",
  "nyilvantartasi_szam",
  "megbizas_targya",
  "plusz_afa",
  "email",
];

const BACK_TARGETS: Record<string, { href: string; label: string }> = {
  vagok: { href: "/csapat/vagok", label: "Vágók" },
  belsosok: { href: "/csapat/belsosok", label: "Belsősök" },
};

const PAGE = "/csapat";

export default async function EmployeeDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ from?: string }>;
}) {
  const { id } = await params;
  const { from } = await searchParams;
  const employeeId = Number(id);
  const employee = await getRecord(ENTITY_PATHS.employee, employeeId);
  if (!employee) notFound();

  const backTarget = (from && BACK_TARGETS[from]) || { href: "/csapat", label: "Külsős" };

  const [
    rates,
    timesheets,
    expenses,
    contracts,
    deliverables,
    campaigns,
    documents,
    belsosTigek,
    utomunkaIdo,
    visibleFields,
    fieldTypes,
    dbTabs,
    pagePermissions,
  ] = await Promise.all([
      getRelated(ENTITY_PATHS.rate, { employee_id: employeeId }),
      getRelated(ENTITY_PATHS.timesheet, { employee_id: employeeId }),
      getRelated(ENTITY_PATHS.expense, { employee_id: employeeId }),
      getRelated(ENTITY_PATHS.contract, { employee_id: employeeId }),
      getRelated(ENTITY_PATHS.deliverable, { vago_employee_id: employeeId }),
      getRelated(ENTITY_PATHS.campaign, { felelos_employee_id: employeeId }),
      getEmployeeDocuments(employeeId),
      getBelsosTigForEmployee(employeeId),
      getUtomunkaIdo(employeeId),
      getVisibleFields("employee"),
      getFieldTypes("employee"),
      getDetailTabs("employee"),
      getMyPagePermissions(),
    ]);

  const vallalkozasFieldKeys = visibleFields
    ? VALLALKOZAS_FIELD_KEYS.filter((k) => visibleFields.includes(k))
    : VALLALKOZAS_FIELD_KEYS;

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath: `${ENTITY_PATHS.employee}/${employee.id}`,
    record: employee,
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
    alwaysHidden: ["hashed_password", ...VALLALKOZAS_FIELD_KEYS],
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href={backTarget.href} label={backTarget.label} />
        <h1 className="text-lg font-medium text-text-primary">{String(employee.full_name ?? `Crew tag #${employee.id}`)}</h1>

        <DetailSections sections={tabs} />

        {/* Az alapadatok ALATT, összecsukva: mennyit vágott hónapról hónapra,
            hónapon belül projektenként (lásd UtomunkaIdoHavonta). Felül az
            adatlap maradjon, ez a hosszú lista ne tolja le. */}
        {utomunkaIdo.length > 0 && (
          <CollapsibleCard title="Utómunkával töltött idő havonta">
            <UtomunkaIdoHavonta honapok={utomunkaIdo} />
          </CollapsibleCard>
        )}

        {vallalkozasFieldKeys.length > 0 && (
          <Card title="Vállalkozás adatok">
            <EditableDetailGrid
              patchPath={`${ENTITY_PATHS.employee}/${employee.id}`}
              fields={toEditableDetailFields(employee, [], vallalkozasFieldKeys, fieldTypes)}
            />
            <div className={vallalkozasFieldKeys.length > 0 ? "mt-4 border-t border-border pt-4" : ""}>
              <p className="mb-2 text-[11px] text-text-muted">Munkaszerződés</p>
              <MunkaszerzodesUpload employeeId={employee.id} documents={documents} />
            </div>
          </Card>
        )}

        {belsosTigek.length > 0 && (
          <Card title={`Belsős TIG-ek (${belsosTigek.length})`}>
            <BelsosTigEmployeeList records={belsosTigek} />
          </Card>
        )}

        <Card title={`Díjak (${rates.length})`}>
          <RelatedTable
            rows={rates}
            emptyText="Nincs felvett díj ehhez a crew taghoz."
            entityKey="rate"
            deleteBasePath={ENTITY_PATHS.rate}
          />
        </Card>

        <Card title={`Munkaidő-elszámolások (${timesheets.length})`}>
          <RelatedTable
            rows={timesheets}
            emptyText="Nincs munkaidő-elszámolás ehhez a crew taghoz."
            entityKey="timesheet"
            deleteBasePath={ENTITY_PATHS.timesheet}
          />
        </Card>

        <Card title={`Kiadások (${expenses.length})`}>
          <RelatedTable
            rows={expenses}
            emptyText="Nincs kiadás ehhez a crew taghoz."
            getHref={(e) => `/penzugyek/kiadas/${e.id}`}
            deleteBasePath={ENTITY_PATHS.expense}
          />
        </Card>

        <Card title={`Szerződések (${contracts.length})`}>
          <RelatedTable
            rows={contracts}
            emptyText="Nincs szerződés ehhez a crew taghoz."
            getHref={(c) => `/szerzodesek/${c.id}`}
            deleteBasePath={ENTITY_PATHS.contract}
          />
        </Card>

        <Card title={`Vágott anyagok (${deliverables.length})`}>
          <RelatedTable
            rows={deliverables}
            emptyText="Nincs vágandó anyag ehhez a crew taghoz."
            getHref={(d) => `/utomunka/${d.id}`}
            deleteBasePath={ENTITY_PATHS.deliverable}
          />
        </Card>

        <Card title={`Felelős kampányok (${campaigns.length})`}>
          <RelatedTable
            rows={campaigns}
            emptyText="Nincs kampány ehhez a crew taghoz."
            getHref={(c) => `/kampanyok/${c.id}`}
            deleteBasePath={ENTITY_PATHS.campaign}
          />
        </Card>
      </div>
    </div>
  );
}
