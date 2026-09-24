import { Card } from "@/components/Card";
import { DataTable, type Column } from "@/components/DataTable";
import { EditableBooleanCell } from "@/components/EditableBooleanCell";
import { EditableTableCell } from "@/components/EditableTableCell";
import { HazipenztarNullazas } from "@/components/finance/HazipenztarNullazas";
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
  type HazipenztarTipus,
  type KpOsszesites,
} from "@/lib/api";
import { formatHuf } from "@/lib/penz";
import { canDoAction } from "@/lib/permissions";
import { ArrowDownLeft, ArrowLeftRight, ArrowUpRight, EyeOff, Wallet } from "lucide-react";

const PAGE = "/penzugyek";

const TIPUS: Record<HazipenztarTipus, { cimke: string; tone: "teal" | "blue" | "orange" | "danger" }> = {
  bevetel: { cimke: "Bevétel", tone: "teal" },
  atvezetes: { cimke: "Átvezetés (ATM)", tone: "blue" },
  kiadas: { cimke: "Kiadás", tone: "orange" },
  fekete_kiadas: { cimke: "Fekete kiadás", tone: "danger" },
};

/** HÁZIPÉNZTÁR: minden készpénz-mozgás egy listában, időrendben, futó
 * egyenleggel. Pontosan négyféle tétel mozgatja (lásd backend
 * services/kassza.py):
 *
 * - BEVÉTEL: csak készpénzes projektkód-kifizetés (a projektkód számla-
 *   lépésénél „Kifizetve / Készpénz”) - itt nem vehető fel kézzel;
 * - ÁTVEZETÉS: ATM-felvétel - a házipénztár nő, a bankszámla csökken, kiadás
 *   nem keletkezik;
 * - KIADÁS: készpénzes kiadás, amihez van vagy lesz számla;
 * - FEKETE KIADÁS: készpénzes kiadás, amire rányomták, hogy sosem lesz
 *   számlája.
 *
 * A számokat a szerver adja, ugyanabból a számításból, mint a Pénzügyek
 * kártyája - így a két felület nem mondhat mást ugyanarról a dobozról. */
export default async function HazipenztarPage() {
  const [naplo, currentUser, pagePermissions, projectCodes] = await Promise.all([
    getKpNaplo(),
    getCurrentUser(),
    getMyPagePermissions(),
    getProjectCodeOptions(),
  ]);
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const ures: KpOsszesites = {
    bevetel: 0,
    bevetel_db: 0,
    atvezetes: 0,
    atvezetes_db: 0,
    sima_kiadas: 0,
    sima_kiadas_db: 0,
    fekete_kiadas: 0,
    fekete_kiadas_db: 0,
    be: 0,
    ki: 0,
    egyenleg: 0,
  };
  const osszes = naplo?.osszes ?? ures;

  // A táblázat a LEGFRISSEBBEL kezd; a futó egyenleg ettől még időrendi - a
  // szerver a sorhoz számolta. A forrás-azonosítók ütközhetnek (egy kiadás és
  // egy bevétel is lehet #12), ezért a DataTable sorszámot kap, az eredeti
  // azonosító `forrasId` alatt marad a szerkesztéshez/törléshez.
  const megjelenitett = [...(naplo?.sorok ?? [])].reverse().map((sor, index) => ({ ...sor, forrasId: sor.id, id: index }));
  type Sor = (typeof megjelenitett)[number];

  const patchUt = (s: Sor) =>
    s.forras === "kp_forgalom" ? `${ENTITY_PATHS.kpForgalom}/${s.forrasId}` : `${ENTITY_PATHS.expense}/${s.forrasId}`;
  // Itt csak az ÁTVEZETÉS szerkeszthető helyben; a kiadás a saját adatlapján
  // (a sor rá visz), a bevétel a projektkód számla-lépésénél.
  const helybenSzerkesztheto = (s: Sor) => canEdit && s.forras === "kp_forgalom";

  const oszlopok: Column<Sor>[] = [
    {
      header: "Dátum",
      render: (s) =>
        helybenSzerkesztheto(s) ? (
          <EditableTableCell patchPath={patchUt(s)} field="kiadas_datuma" value={s.datum} type="date" />
        ) : (
          (s.datum ?? "–")
        ),
      sortAccessor: (s) => s.datum,
    },
    {
      header: "Megnevezés",
      render: (s) =>
        helybenSzerkesztheto(s) ? (
          <EditableTableCell patchPath={patchUt(s)} field="megnevezes" value={s.megnevezes} />
        ) : (
          s.megnevezes
        ),
      sortAccessor: (s) => s.megnevezes,
    },
    {
      header: "Típus",
      render: (s) => <StatusBadge label={TIPUS[s.tipus].cimke} tone={TIPUS[s.tipus].tone} />,
      sortAccessor: (s) => s.tipus,
    },
    {
      header: "Projektkód",
      render: (s) => s.projektkod ?? "–",
      sortAccessor: (s) => s.projektkod,
    },
    {
      header: "Összeg",
      align: "right",
      render: (s) =>
        helybenSzerkesztheto(s) ? (
          <span className={s.ki > 0 ? "text-text-orange" : "text-text-teal"}>
            {s.ki > 0 ? "−" : "+"}
            <EditableTableCell patchPath={patchUt(s)} field="osszeg" value={s.be || s.ki} type="number" />
          </span>
        ) : s.ki > 0 ? (
          <span className="text-text-orange">−{formatHuf(s.ki)}</span>
        ) : (
          <span className="text-text-teal">+{formatHuf(s.be)}</span>
        ),
      sortAccessor: (s) => s.be - s.ki,
    },
    {
      header: "Egyenleg",
      align: "right",
      render: (s) => <span className="tabular-nums text-text-secondary">{formatHuf(s.egyenleg)}</span>,
    },
    {
      // Kiadásnál: rányomható, hogy SOSEM lesz számlája - ettől lesz fekete.
      header: "Sosem lesz számla",
      align: "right",
      render: (s) =>
        s.forras !== "kiadas" ? (
          <span className="text-text-muted">–</span>
        ) : canEdit ? (
          <EditableBooleanCell patchPath={patchUt(s)} field="nincs_szamla" value={s.tipus === "fekete_kiadas"} />
        ) : s.tipus === "fekete_kiadas" ? (
          "Igen"
        ) : (
          "–"
        ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
          <StatCard
            label="Házipénztár egyenlege"
            value={formatHuf(osszes.egyenleg)}
            icon={Wallet}
            tone={osszes.egyenleg < 0 ? "danger" : "accent"}
            megjegyzes="Ennyi készpénznek kell most nálunk lennie"
          />
          <StatCard
            label="Bevétel – KP projektkód-kifizetés"
            value={formatHuf(osszes.bevetel)}
            icon={ArrowDownLeft}
            tone="teal"
            megjegyzes={`${osszes.bevetel_db} tétel`}
          />
          <StatCard
            label="Átvezetés – ATM-felvétel"
            value={formatHuf(osszes.atvezetes)}
            icon={ArrowLeftRight}
            tone="blue"
            megjegyzes={`${osszes.atvezetes_db} tétel · a bankszámláról, nem kiadás`}
          />
          <StatCard
            label="Kiadás (van / lesz számla)"
            value={formatHuf(osszes.sima_kiadas)}
            icon={ArrowUpRight}
            tone="orange"
            megjegyzes={`${osszes.sima_kiadas_db} tétel`}
          />
          <StatCard
            label="Fekete kiadás (sosem lesz számla)"
            value={formatHuf(osszes.fekete_kiadas)}
            icon={EyeOff}
            tone={osszes.fekete_kiadas > 0 ? "danger" : "default"}
            megjegyzes={`${osszes.fekete_kiadas_db} tétel · nem elszámolható költség`}
          />
        </div>

        <Card title={`Házipénztár (${megjelenitett.length} mozgás)`}>
          <p className="mb-3 text-[12.5px] text-text-muted">
            Egyenleg = bevétel + átvezetés − kiadás − fekete kiadás, bruttóban, 2026.01.01 óta. <b>Bevétel</b> csak a
            projektkód készpénzes kifizetéséből kerülhet ide (projektkód → Számla → Kifizetve, fizetési mód: Készpénz).{" "}
            <b>Átvezetés</b> az ATM-ből felvett készpénz: a házipénztár nő, a bankszámla egyenlege csökken, kiadás nem
            keletkezik. A <b>kiadás</b> fekete, ha rányomjátok, hogy sosem lesz számlája.
          </p>
          {canCreate && (
            <div className="mb-3 flex flex-wrap items-start gap-3">
              <QuickCreateForm
                postPath={ENTITY_PATHS.kpForgalom}
                addLabel="+ Átvezetés (ATM-felvétel)"
                presetFields={{ forgalom: "atvezetes" }}
                fields={[
                  { name: "megnevezes", label: "Megnevezés", required: true, defaultValue: "KP felvétel ATM" },
                  { name: "kiadas_datuma", label: "Dátum", type: "date", required: true },
                  { name: "osszeg", label: "Összeg (Ft)", type: "number", required: true },
                ]}
              />
              <QuickCreateForm
                postPath={ENTITY_PATHS.expense}
                addLabel="+ Készpénzes kiadás"
                // Készpénzben, dátummal: a pénz kiment a dobozból, tehát
                // rögtön kifizetett (lásd backend routes/finance
                // _expense_before_create).
                presetFields={{ kifizetes_modja: "Készpénz", tipus: "egyeb", kesz: true }}
                fajlFeltoltes={{
                  entityType: "expense",
                  kategoria: "szamla",
                  nincsKapcsolo: { name: "nincs_szamla", cimke: "Sosem lesz számlája (fekete kiadás)" },
                }}
                fields={[
                  { name: "megnevezes", label: "Kinek / mire", required: true },
                  { name: "kiadas_leiras", label: "Megjegyzés" },
                  { name: "fizetes_datuma", label: "Dátum", type: "date", required: true },
                  { name: "brutto", label: "Kifizetett összeg (bruttó, Ft)", type: "number", required: true },
                  { name: "netto", label: "Nettó (ha van ÁFA-s számla)", type: "number" },
                  {
                    name: "project_code_id",
                    label: "Projektkód",
                    type: "select",
                    options: projectCodes.map((pc) => ({ value: pc.id, label: pc.projektkod })),
                  },
                ]}
              />
            </div>
          )}
          <DataTable<Sor>
            rows={megjelenitett}
            columns={oszlopok}
            emptyText="A házipénztár üres – vegyél fel egy ATM-átvezetést vagy készpénzes kiadást, vagy rögzíts egy készpénzes projektkód-kifizetést."
            getHref={(s) => s.href ?? ""}
            deleteHref={
              canDelete ? (s) => (s.forras === "bevetel" ? "" : patchUt(s)) : undefined
            }
            filterable
          />
        </Card>

        {canDelete && (
          <Card title="Nullázás">
            <p className="mb-3 text-[12.5px] text-text-muted">
              Minden készpénzes tétel törlése a Kiadások, a Bevételek és a Házipénztár közül, hogy a pénztár nulláról
              induljon. Előtte letöltődik egy teljes mentés, amiből bármelyik tétel visszaállítható.
            </p>
            <HazipenztarNullazas />
          </Card>
        )}
      </div>
    </div>
  );
}
