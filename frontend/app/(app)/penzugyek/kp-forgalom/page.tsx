import { Card } from "@/components/Card";
import { DataTable, type Column } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { KpForgalomSzamlaCella } from "@/components/finance/KpForgalomSzamlaCella";
import { TorolMindenMozgastButton } from "@/components/finance/TorolMindenMozgastButton";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getCurrentUser,
  getKpNaplo,
  getMyPagePermissions,
  getProjectCodeOptions,
  type KpOsszesites,
} from "@/lib/api";
import { formatHuf, PENZNEMEK } from "@/lib/penz";
import { canDoAction } from "@/lib/permissions";
import { ArrowDownLeft, ArrowUpRight, EyeOff, Receipt } from "lucide-react";

const PAGE = "/penzugyek";

/** A KP forgalom sor IRÁNYA. A "fedezet" egy BEVÉTEL-jellegű sor, aminél a
 * felhasználó kifejezetten jelzi, hogy ez számla nélküli bevétel, ami a
 * fekete kiadást fedezi (lásd backend services/kassza.py kp_forgalom_iranya -
 * a "fedezet" is bevétel-irányban számol, csak a Számla oszlopban másképp
 * jelenik meg). */
const IRANY_OPCIOK = ["kiadas", "bevetel", "fedezet"] as const;
const IRANY_CIMKEK: Record<string, string> = { kiadas: "Kiadás", bevetel: "Bevétel", fedezet: "Fedezet" };

/** KP FORGALOM: minden készpénz-mozgás egy listában, időrendben - és a
 * LEGÁLIS/FEKETE bontás.
 *
 * A készpénznél nem csak az számít, mennyi mozdult, hanem az is, van-e mögötte
 * SZÁMLA:
 *
 * - a számlás kiadás elszámolható költség: ez a legális oldal;
 * - a számla nélküli kiadást nem lehet elszámolni - ez a "fekete";
 * - a számla nélküli BEVÉTEL viszont épp ezt fedezi: ami számla nélkül jött
 *   be, az számla nélkül is elkölthető.
 *
 *       fekete egyenleg = számla nélküli KIADÁS - számla nélküli BEVÉTEL
 *
 * A KASSZA egyenlege ettől független: az a teljes forgalom különbsége, és
 * annak kell megegyeznie azzal, ami fizikailag a dobozban van.
 *
 * A számokat a szerver adja (lásd backend services/kassza.py), ugyanabból a
 * számításból, mint a Pénzügyek kassza-kártyája - így a két felület nem
 * mondhat mást ugyanarról a dobozról. */
export default async function KpForgalomPage() {
  const [naplo, currentUser, pagePermissions, projectCodes] = await Promise.all([
    getKpNaplo(),
    getCurrentUser(),
    getMyPagePermissions(),
    getProjectCodeOptions(),
  ]);
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const sorok = naplo?.sorok ?? [];
  const ures: KpOsszesites = {
    be_szamlaval: 0,
    be_szamla_nelkul: 0,
    ki_szamlaval: 0,
    ki_szamla_nelkul: 0,
    be_szamlaval_db: 0,
    be_szamla_nelkul_db: 0,
    ki_szamlaval_db: 0,
    ki_szamla_nelkul_db: 0,
    be_atvezetes: 0,
    ki_atvezetes: 0,
    be_atvezetes_db: 0,
    ki_atvezetes_db: 0,
    be: 0,
    ki: 0,
    egyenleg: 0,
    fekete_egyenleg: 0,
  };
  const idei = naplo?.idei ?? ures;
  const osszes = naplo?.osszes ?? ures;
  const jeloletlen = (naplo?.jeloletlen_kiadas ?? 0) + (naplo?.jeloletlen_bevetel ?? 0);

  // A táblázat a LEGFRISSEBBEL kezd: a napi munkában a legutóbbi mozgás a
  // kérdés. A futó egyenleg ettől még időrendi - a szerver a sorhoz számolta,
  // nem a megjelenítés sorrendjéhez.
  const megjelenitett = [...sorok]
    .reverse()
    // A DataTable egyedi id-t vár; a forrás-azonosítók viszont ütközhetnek
    // (egy kiadás és egy bevétel is lehet #12), ezért kapnak sorszámot - az
    // EREDETI forrás-id-t forrasId alatt megtartjuk, mert a KP forgalom
    // sorok helyben szerkesztéséhez/törléséhez az kell (lásd oszlopok lent).
    .map((sor, index) => ({ ...sor, forrasId: sor.id, id: index }));

  type Sor = (typeof megjelenitett)[number];

  const oszlopok: Column<Sor>[] = [
    {
      header: "Dátum",
      render: (s) =>
        // Csak a Notionből örökölt KP forgalom sorok szerkeszthetők itt - a
        // kiadás/bevétel forrású sorok a Pénzügyeken javíthatók (lásd fenti
        // magyarázó szöveg).
        canEdit && s.forras === "kp_forgalom" ? (
          <EditableTableCell
            patchPath={`${ENTITY_PATHS.kpForgalom}/${s.forrasId}`}
            field="kiadas_datuma"
            value={s.datum}
            type="date"
          />
        ) : (
          (s.datum ?? "–")
        ),
      sortAccessor: (s) => s.datum,
    },
    {
      header: "Megnevezés",
      render: (s) =>
        canEdit && s.forras === "kp_forgalom" ? (
          <EditableTableCell
            patchPath={`${ENTITY_PATHS.kpForgalom}/${s.forrasId}`}
            field="megnevezes"
            value={s.megnevezes}
          />
        ) : (
          s.megnevezes
        ),
      sortAccessor: (s) => s.megnevezes,
    },
    {
      header: "Típus",
      render: (s) =>
        // Az ÁTVEZETÉS (ATM-felvétel) nem bevétel: a saját pénzünk került át a
        // bankszámláról a kasszába. Ki is írjuk, mert a sor egyébként
        // megtévesztően nagy "bevételnek" látszana.
        s.atvezetes ? (
          <StatusBadge label="Átvezetés (ATM)" tone="blue" />
        ) : canEdit && s.forras === "kp_forgalom" ? (
          <EditableStatusBadge
            patchPath={`${ENTITY_PATHS.kpForgalom}/${s.forrasId}`}
            field="forgalom"
            value={s.forgalom ?? (s.ki > 0 ? "kiadas" : "bevetel")}
            options={[...IRANY_OPCIOK]}
            labels={IRANY_CIMKEK}
          />
        ) : (
          <StatusBadge label={s.ki > 0 ? "Kiadás" : "Bevétel"} tone={s.ki > 0 ? "orange" : "teal"} />
        ),
      sortAccessor: (s) => (s.atvezetes ? "atvezetes" : s.ki > 0 ? "kiadas" : "bevetel"),
    },
    {
      header: "Projektkód",
      render: (s) =>
        // Csak "kp_forgalom" forrásnál választható itt - a Kiadás/Bevétel
        // forrású soroké a saját projektkódjukból jön, a Pénzügyeken javítható.
        canEdit && s.forras === "kp_forgalom" ? (
          <EditableStatusBadge
            patchPath={`${ENTITY_PATHS.kpForgalom}/${s.forrasId}`}
            field="project_code_id"
            value={s.project_code_id !== null ? String(s.project_code_id) : null}
            options={projectCodes.map((pc) => String(pc.id))}
            labels={Object.fromEntries(projectCodes.map((pc) => [String(pc.id), pc.projektkod]))}
            placeholder="Nincs megadva"
          />
        ) : (
          (s.projektkod ?? "–")
        ),
      sortAccessor: (s) => s.projektkod,
    },
    {
      header: "Forintban",
      align: "right",
      render: (s) => {
        const jel = s.ki > 0 ? "text-text-orange" : "text-text-teal";
        const ertek = s.ki > 0 ? s.ki : s.be;
        return (
          <div>
            <span className={jel}>
              {canEdit && s.forras === "kp_forgalom" && !s.atvezetes ? (
                <EditableTableCell
                  patchPath={`${ENTITY_PATHS.kpForgalom}/${s.forrasId}`}
                  field="osszeg"
                  value={ertek}
                  type="number"
                />
              ) : (
                formatHuf(ertek)
              )}
            </span>
            {/* MIBŐL lett a forint összeg - devizás felvezetésnél az eredeti
                összeg és árfolyam, egyébként simán a pénznem (lásd backend
                services/penznem.py). Csak a KP forgalom soroknál van ilyen
                nyoma - a Kiadás/Bevétel forrásúaknak saját, más elrendezésű
                jelzőjük van a Pénzügyeken. */}
            {s.forras === "kp_forgalom" && !s.atvezetes && (
              <div className="text-[11px] text-text-muted">
                {s.eredeti_penznem
                  ? `${(s.eredeti_osszeg ?? 0).toLocaleString("hu-HU")} ${s.eredeti_penznem} × ${
                      s.arfolyam === null ? "?" : s.arfolyam.toLocaleString("hu-HU")
                    }`
                  : (s.penznem ?? "HUF")}
              </div>
            )}
          </div>
        );
      },
      sortAccessor: (s) => (s.ki > 0 ? -s.ki : s.be),
    },
    {
      // Ez dönti el, a legális vagy a fekete oldalra kerül-e a tétel.
      header: "Számla",
      align: "right",
      render: (s) =>
        // Átvezetésnél a bizonylat a banki kivonat - se legális, se fekete.
        s.atvezetes ? (
          <span className="text-text-muted">–</span>
        ) : s.forras === "kp_forgalom" ? (
          // A Notionből örökölt KP forgalom soroknak eddig nem volt saját
          // bizonylat-feltöltési felületük - ez nyit egy kis ablakot rá.
          <KpForgalomSzamlaCella
            forrasId={s.forrasId}
            vanSzamla={s.van_szamla}
            csatolmanyok={s.csatolmanyok}
            canEdit={canEdit}
            canDelete={canDelete}
          />
        ) : s.van_szamla ? (
          <StatusBadge label="Van" tone="success" />
        ) : s.be > 0 ? (
          // A számla nélküli BEVÉTEL nem hiányosság, hanem FEDEZET: ez az a
          // készpénz, amiből a számla nélküli kiadás fedezhető - a fekete
          // egyenleget csökkenti (lásd backend services/kassza.py). Egy
          // "Nincs" figyelmeztetés itt félrevezető volna.
          <StatusBadge label="Fedezet" tone="blue" />
        ) : (
          <StatusBadge label="Nincs" tone="warning" />
        ),
      sortAccessor: (s) => (s.atvezetes ? -1 : s.van_szamla ? 1 : 0),
    },
  ];

  /** Egy sor a legális/fekete táblában. */
  function Sorpar({
    cimke,
    ideiErtek,
    osszesErtek,
    ideiDb,
    kiemelt = false,
    hangsulyos = false,
  }: {
    cimke: string;
    ideiErtek: number;
    osszesErtek: number;
    ideiDb?: number;
    kiemelt?: boolean;
    hangsulyos?: boolean;
  }) {
    return (
      <tr className={kiemelt ? "border-t border-border" : undefined}>
        <td className={`py-1.5 text-[13px] ${hangsulyos ? "text-text-primary" : "text-text-secondary"}`}>
          {cimke}
          {ideiDb !== undefined && <span className="ml-1.5 text-[11.5px] text-text-muted">{ideiDb} tétel</span>}
        </td>
        <td
          className={`py-1.5 text-right tabular-nums text-[13px] ${
            hangsulyos ? "font-medium text-text-primary" : "text-text-primary"
          }`}
        >
          {formatHuf(ideiErtek)}
        </td>
        <td className="py-1.5 text-right tabular-nums text-[13px] text-text-secondary">
          {formatHuf(osszesErtek)}
        </td>
      </tr>
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        {/* A NÉGY SZÁM, amiből a készpénz képe áll - idei évre. */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Idei bevétel – van számla"
            value={formatHuf(idei.be_szamlaval)}
            icon={Receipt}
            tone="teal"
            megjegyzes={`${idei.be_szamlaval_db} tétel`}
          />
          <StatCard
            label="Idei bevétel – fedezet (nincs számla)"
            value={formatHuf(idei.be_szamla_nelkul)}
            icon={ArrowDownLeft}
            tone="blue"
            megjegyzes={`${idei.be_szamla_nelkul_db} tétel · ez fedezi a fekete kiadást`}
          />
          <StatCard
            label="Idei kiadás – összesen"
            value={formatHuf(idei.ki)}
            icon={ArrowUpRight}
            tone="orange"
            megjegyzes={`ebből ${formatHuf(idei.ki_szamlaval)} számlás`}
          />
          <StatCard
            label="Idei FEKETE kiadás (nincs számla)"
            value={formatHuf(idei.ki_szamla_nelkul)}
            icon={EyeOff}
            tone={idei.ki_szamla_nelkul > 0 ? "danger" : "default"}
            megjegyzes={`${idei.ki_szamla_nelkul_db} tétel · nem elszámolható költség`}
          />
        </div>

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <Card title="Legális és fekete készpénz">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-2 text-left text-[11.5px] font-medium uppercase tracking-wide text-text-muted">
                    Tétel
                  </th>
                  <th className="pb-2 text-right text-[11.5px] font-medium uppercase tracking-wide text-text-muted">
                    Idén
                  </th>
                  <th className="pb-2 text-right text-[11.5px] font-medium uppercase tracking-wide text-text-muted">
                    Összesen
                  </th>
                </tr>
              </thead>
              <tbody>
                <Sorpar
                  cimke="Bevétel – van számla (legális)"
                  ideiErtek={idei.be_szamlaval}
                  osszesErtek={osszes.be_szamlaval}
                  ideiDb={idei.be_szamlaval_db}
                />
                <Sorpar
                  cimke="Bevétel – nincs számla (fedezet)"
                  ideiErtek={idei.be_szamla_nelkul}
                  osszesErtek={osszes.be_szamla_nelkul}
                  ideiDb={idei.be_szamla_nelkul_db}
                />
                <Sorpar
                  cimke="Átvezetés – ATM-felvétel (se nem bevétel, se nem költés)"
                  ideiErtek={idei.be_atvezetes}
                  osszesErtek={osszes.be_atvezetes}
                  ideiDb={idei.be_atvezetes_db}
                />
                <Sorpar cimke="Összes bevétel" ideiErtek={idei.be} osszesErtek={osszes.be} kiemelt hangsulyos />
                <Sorpar
                  cimke="Kiadás – van számla (legális)"
                  ideiErtek={idei.ki_szamlaval}
                  osszesErtek={osszes.ki_szamlaval}
                  ideiDb={idei.ki_szamlaval_db}
                  kiemelt
                />
                <Sorpar
                  cimke="Kiadás – nincs számla (fekete)"
                  ideiErtek={idei.ki_szamla_nelkul}
                  osszesErtek={osszes.ki_szamla_nelkul}
                  ideiDb={idei.ki_szamla_nelkul_db}
                />
                <Sorpar cimke="Összes kiadás" ideiErtek={idei.ki} osszesErtek={osszes.ki} kiemelt hangsulyos />
                <Sorpar
                  cimke="Fekete egyenleg (fekete kiadás − számla nélküli bevétel)"
                  ideiErtek={idei.fekete_egyenleg}
                  osszesErtek={osszes.fekete_egyenleg}
                  kiemelt
                  hangsulyos
                />
              </tbody>
            </table>
            <p className="mt-3 text-[12px] text-text-muted">
              A számla nélküli KIADÁS az, amit a cég nem tud elszámolni. Amit viszont számla nélkül kaptunk
              készpénzben, az ezt fedezi – a kettő különbsége a „fekete egyenleg". Ha ez negatív, több a számla
              nélküli bevétel, mint a költés: az nem hiány, hanem tartalék.
            </p>
          </Card>

          <Card title="Kassza">
            <div className="mb-4">
              <p className="text-[12.5px] text-text-secondary">Ennyi készpénznek kell most nálunk lennie</p>
              <p
                className={`mt-1 text-[32px] font-semibold leading-none tracking-[-0.03em] tabular-nums ${
                  osszes.egyenleg < 0 ? "text-text-danger" : "text-text-primary"
                }`}
              >
                {formatHuf(osszes.egyenleg)}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <StatCard label="Összes készpénz be" value={formatHuf(osszes.be)} icon={ArrowDownLeft} tone="teal" />
              <StatCard label="Összes készpénz ki" value={formatHuf(osszes.ki)} icon={ArrowUpRight} tone="orange" />
            </div>
            <p className="mt-3 text-[12px] text-text-muted">
              Minden készpénzes bevétel mínusz minden készpénzes kiadás, bruttóban – ennek kell megegyeznie
              azzal, ami fizikailag a dobozban van. Csak a MEGTÖRTÉNT mozgás számít: aminek nincs fizetési
              dátuma, az még nem hiányzik a kasszából.
            </p>
            {jeloletlen > 0 && (
              <p className="mt-2 text-[12px] text-text-warning">
                {jeloletlen} kifizetett tételen nincs megjelölve a fizetési mód – amíg ez így van, az egyenleg
                csak közelítés.
              </p>
            )}
          </Card>
        </div>

        {/* EGY tábla minden készpénz-mozgáshoz: a napló sorai a KIADÁSOKBÓL, a
            BEVÉTELEKBŐL és a Notionből örökölt „KP forgalom" tábla soraiból
            állnak össze. A kiadás/bevétel forrású sorok a Pénzügyeken
            szerkeszthetők (ott saját felületük van); a Notionből örökölt KP
            forgalom sorok viszont eddig SEHOL nem voltak javíthatók, pedig
            ezeknél van a legtöbb elcsúszás - ezért ITT, helyben
            szerkeszthetők/törölhetők/felvehetők. */}
        <Card
          title={`KP forgalom (${megjelenitett.length} mozgás)`}
          actions={canDelete ? <TorolMindenMozgastButton darabszam={megjelenitett.length} /> : undefined}
        >
          <p className="mb-3 text-[12.5px] text-text-muted">
            Minden készpénz-mozgás időrendben. A KIADÁS és BEVÉTEL forrású sorok a{" "}
            <a href="/penzugyek" className="text-text-accent hover:underline">
              Pénzügyeken
            </a>{" "}
            szerkeszthetők; a Notionből örökölt „KP forgalom" sorok itt, helyben szerkeszthetők/törölhetők/
            felvehetők - ezeknél volt a legtöbb elcsúszás az importált adatban.
            {(naplo?.kp_forgalom_kiadashoz_kotve ?? 0) > 0 && (
              <>
                {" "}
                {naplo?.kp_forgalom_kiadashoz_kotve} KP forgalom sor kimarad, mert egy konkrét kiadáshoz kötődik:
                ugyanaz a pénzmozgás már szerepel a kiadás soraként, beszámítva kétszer vonódna le.
              </>
            )}
          </p>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.kpForgalom}
              addLabel="+ Új KP forgalom tétel"
              fields={[
                { name: "megnevezes", label: "Megnevezés", required: true },
                { name: "kiadas_datuma", label: "Dátum", type: "date" },
                {
                  name: "forgalom",
                  label: "Típus",
                  type: "select",
                  defaultValue: "kiadas",
                  options: IRANY_OPCIOK.map((o) => ({ value: o, label: IRANY_CIMKEK[o] })),
                },
                { name: "osszeg", label: "Forintban", type: "number" },
                {
                  name: "penznem",
                  label: "Pénznem",
                  type: "select",
                  defaultValue: "HUF",
                  options: PENZNEMEK.map((p) => ({ value: p, label: p })),
                },
                {
                  name: "arfolyam",
                  label: "Árfolyam (Ft)",
                  type: "number",
                  required: true,
                  // Csak devizánál kérdezzük: forintnál nincs mit átváltani -
                  // a szerver ebből számolja ki a forintban mezőt.
                  showIf: { field: "penznem", noneOf: ["", "HUF"] },
                },
                {
                  name: "van_szamla",
                  label: "Számla",
                  type: "select",
                  defaultValue: "false",
                  options: [
                    { value: "false", label: "Nincs" },
                    { value: "true", label: "Van" },
                  ],
                },
                {
                  name: "project_code_id",
                  label: "Projekt kiadás",
                  type: "select",
                  options: projectCodes.map((pc) => ({ value: pc.id, label: pc.projektkod })),
                },
              ]}
            />
          )}
          <DataTable<Sor>
            rows={megjelenitett}
            columns={oszlopok}
            emptyText="Még nincs egyetlen készpénzes mozgás sem – a Pénzügyeken a kiadás/bevétel fizetési módját kell Készpénzre állítani."
            getHref={(s) => s.href ?? ""}
            deleteHref={canDelete ? (s) => (s.forras === "kp_forgalom" ? `${ENTITY_PATHS.kpForgalom}/${s.forrasId}` : "") : undefined}
            filterable
          />
        </Card>
      </div>
    </div>
  );
}
