import { notFound } from "next/navigation";
import { Clapperboard, FileText, Scissors, Wallet } from "lucide-react";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailSections } from "@/components/DetailSections";
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { MunkaszerzodesUpload } from "@/components/MunkaszerzodesUpload";
import { RelatedTable } from "@/components/RelatedTable";
import { UtomunkaIdoHavonta } from "@/components/UtomunkaIdoHavonta";
import { HaviKoltsegek } from "@/components/crew/HaviKoltsegek";
import { EgyebKiadasok } from "@/components/crew/EgyebKiadasok";
import { KulsosMunkak } from "@/components/crew/KulsosMunkak";
import { Reszvetel } from "@/components/crew/Reszvetel";
import { VagottAnyagokLista } from "@/components/crew/VagottAnyagokLista";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getAttachments,
  getCurrentUser,
  getDetailTabs,
  getEmployeeDocuments,
  getEmployeeKoltsegek,
  getFieldTypes,
  getKulsosMunkak,
  getMyPagePermissions,
  getProjectCodes,
  getReszvetel,
  getRecord,
  getRelated,
  getUtomunkaIdo,
  getVagottAnyagok,
  getVisibleFields,
} from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";
import { buildFieldTabs } from "@/lib/detailTabs";
import { canDoAction } from "@/lib/permissions";

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
    expenses,
    contracts,
    vagottAnyagok,
    documents,
    attachments,
    koltsegek,
    munkak,
    projektkodok,
    reszvetel,
    utomunkaIdo,
    visibleFields,
    fieldTypes,
    dbTabs,
    pagePermissions,
    currentUser,
  ] = await Promise.all([
    getRelated(ENTITY_PATHS.rate, { employee_id: employeeId }),
    getRelated(ENTITY_PATHS.expense, { employee_id: employeeId }),
    getRelated(ENTITY_PATHS.contract, { employee_id: employeeId }),
    getVagottAnyagok(employeeId),
    getEmployeeDocuments(employeeId),
    getAttachments("employee", employeeId),
    getEmployeeKoltsegek(employeeId),
    getKulsosMunkak(employeeId),
    getProjectCodes(),
    getReszvetel(employeeId),
    getUtomunkaIdo(employeeId),
    getVisibleFields("employee"),
    getFieldTypes("employee"),
    getDetailTabs("employee"),
    getMyPagePermissions(),
    getCurrentUser(),
  ]);

  const vallalkozasFieldKeys = visibleFields
    ? VALLALKOZAS_FIELD_KEYS.filter((k) => visibleFields.includes(k))
    : VALLALKOZAS_FIELD_KEYS;

  // A külsős és a belsős elszámolása alapvetően különbözik (havi bér vs.
  // projektenkénti szerződés + TIG), ezért más blokkok kerülnek az adatlapra.
  const kulsos = employee.tipus === "kulsos";
  const szerkeszthet = canDoAction(currentUser?.role, pagePermissions, PAGE, "edit");
  const torolhet = canDoAction(currentUser?.role, pagePermissions, PAGE, "delete");
  const projektkodOpciok = projektkodok.map((p) => ({ id: p.id, projektkod: p.projektkod }));
  // Az "Egyéb kiadások" tábla a kiadás projektkód-azonosítójából a KÓDOT írja
  // ki, nem a nyers id-t - ehhez kell a feloldás.
  const projektkodNevek = Object.fromEntries(projektkodok.map((p) => [p.id, p.projektkod]));

  /* A BELSŐSÖK havi bérelszámolása. A külsősöknél ez nem értelmezhető:
     ők projektenként dolgoznak (eseti szerződés vagy keretszerződés), és a
     TIG mondja meg, mennyiért - ezért náluk a lenti munka-blokk áll a
     helyén. */
  const haviKoltsegekTab = {
    key: "havi-koltsegek",
    // A Belsős TIG havi összegei ITT jelennek meg (nincs külön TIG-kártya):
    // ez válaszolja meg, hogy mibe került nekünk ez az ember - és ugyanitt
    // vihetők fel a hónap tételei, amikből a TIG összege összeáll.
    //
    // A név szándékosan egyértelmű: a Notionból örökölt, admin által
    // konfigurált "Kiadások" mezőcsoport (Extra kiadás megnevezés/összeg/
    // dátum) még létezhet az adatlapon - ez váltja ki, de a régit csak a
    // Beállítások > Részletnézet fülek alatt lehet levenni, mert az
    // beállítás, nem kód.
    label: "Havi kiadások",
    content: (
      <Card title="Havi kiadások (alapbér + extrák)" icon={Wallet}>
        <HaviKoltsegek
          employeeId={employee.id}
          evek={koltsegek}
          projektkodok={projektkodOpciok}
          szerkeszthet={szerkeszthet}
          torolhet={torolhet}
        />
        {/* Az alapbéren FELÜLI költségek egy összesítésben: a pénzügyi
            kiadások (számlák) és a havi elszámoláshoz felvitt extrák/
            levonások együtt, egyetlen végösszeggel. */}
        <div className="mt-6 border-t border-border pt-5">
          <p className="t-label mb-3">Egyéb kiadások és havi extrák</p>
          <EgyebKiadasok kiadasok={expenses} koltsegek={koltsegek} projektkodNevek={projektkodNevek} />
        </div>
      </Card>
    ),
  };

  /* A KÜLSŐSÖK elszámolása: miken vett részt, mennyiért, és hol vannak a
     hozzá tartozó papírok (szerződés / TIG / számla). */
  const kulsosMunkakTab = {
    key: "kulsos-munkak",
    label: "Projektek és kifizetések",
    content: (
      <Card title="Projektek és kifizetések" icon={Wallet}>
        <KulsosMunkak
          adat={
            munkak ?? {
              projektek: [],
              osszes_netto: 0,
              osszes_brutto: 0,
              keretszerzodes_id: null,
              keretszerzodes_url: null,
            }
          }
        />
      </Card>
    ),
  };

  /* MINDEN blokk szekcióként megy be, nem a lap aljára fixen kirakva - így az
     admin által beállított sorrend (fogd és vidd) ugyanúgy vonatkozik rájuk,
     mint az adatlap mező-kártyáira. */
  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath: `${ENTITY_PATHS.employee}/${employee.id}`,
    record: employee,
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
    alwaysHidden: ["hashed_password", ...VALLALKOZAS_FIELD_KEYS],
    extraTabs: [
      ...(vallalkozasFieldKeys.length > 0
        ? [
            {
              key: "vallalkozas",
              label: "Vállalkozás adatok",
              content: (
                <Card title="Vállalkozás adatok" icon={FileText}>
                  <EditableDetailGrid
                    patchPath={`${ENTITY_PATHS.employee}/${employee.id}`}
                    fields={toEditableDetailFields(employee, [], vallalkozasFieldKeys, fieldTypes)}
                  />
                  <div className="mt-6 border-t border-border pt-5">
                    <p className="t-label mb-2">Munkaszerződés</p>
                    <MunkaszerzodesUpload employeeId={employee.id} documents={documents} />
                  </div>
                </Card>
              ),
            },
          ]
        : []),
      {
        key: "berezes",
        label: "Bérezés",
        content: (
          <Card title={`Bérezés (${rates.length})`} icon={Wallet}>
            <RelatedTable
              rows={rates}
              emptyText="Nincs felvett bérezés ehhez a crew taghoz."
              entityKey="rate"
              deleteBasePath={ENTITY_PATHS.rate}
            />
          </Card>
        ),
      },
      ...(utomunkaIdo.length > 0
        ? [
            {
              key: "utomunka-ido",
              label: "Utómunkával töltött idő",
              content: (
                <Card title="Utómunkával töltött idő havonta" icon={Scissors}>
                  <UtomunkaIdoHavonta honapok={utomunkaIdo} />
                </Card>
              ),
            },
          ]
        : []),
      {
        // MINDEN munkatársnál: min dolgozott. A forgatások és a vágás egy
        // listában, mert ugyanaz a kérdés - csak más a szerep.
        key: "reszvetel",
        label: "Projektek",
        content: (
          <Card title={`Projektek, amiken részt vett (${reszvetel.length})`} icon={Clapperboard}>
            <Reszvetel sorok={reszvetel} />
          </Card>
        ),
      },
      {
        key: "vagott-anyagok",
        label: "Vágott anyagok",
        content: (
          <Card title={`Vágott anyagok (${vagottAnyagok.length})`} icon={Scissors}>
            <VagottAnyagokLista anyagok={vagottAnyagok} />
          </Card>
        ),
      },
      ...(kulsos ? [kulsosMunkakTab] : [haviKoltsegekTab]),
      {
        key: "szerzodesek",
        label: "Szerződések",
        content: (
          <Card title={`Szerződések (${contracts.length})`} icon={FileText}>
            <RelatedTable
              rows={contracts}
              emptyText="Nincs szerződés ehhez a crew taghoz."
              getHref={(c) => `/szerzodesek/${c.id}`}
              deleteBasePath={ENTITY_PATHS.contract}
            />
            {/* A keretszerződés (és bármi más aláírt papír) fájlja ITT
                tölthető fel, akár több is - a tárolás az R2-n van (lásd
                backend services/attachments.py). */}
            <div className="mt-6 border-t border-border pt-5">
              <p className="t-label mb-3">Keretszerződés és egyéb aláírt dokumentumok</p>
              <DokumentumFeltoltes
                entityType="employee"
                entityId={employee.id}
                attachments={attachments.filter((a) => a.kategoria === "szerzodes")}
                kategoria="szerzodes"
                canEdit={szerkeszthet}
                canDelete={torolhet}
                emptyText="Nincs feltöltött keretszerződés."
              />
            </div>
          </Card>
        ),
      },
    ],
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-8">
        <div className="space-y-2">
          <BackLink href={backTarget.href} label={backTarget.label} />
          <h1 className="t-page">{String(employee.full_name ?? `Crew tag #${employee.id}`)}</h1>
        </div>

        <DetailSections sections={tabs} entityType="employee" canReorder={currentUser?.role === "admin"} />
      </div>
    </div>
  );
}
