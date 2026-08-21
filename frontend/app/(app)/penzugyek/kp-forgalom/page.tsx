import { Card } from "@/components/Card";
import { DataTable, type Column } from "@/components/DataTable";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { getKpNaplo, type KpNaploSor } from "@/lib/api";
import { formatHuf } from "@/lib/penz";
import { ArrowDownLeft, ArrowUpRight, Wallet } from "lucide-react";

/** KP FORGALOM: minden készpénz-mozgás egy listában, időrendben.
 *
 * A Pénzügyek kártyáján csak az EGYENLEG látszik - itt viszont soronként az
 * is, miből jött össze. Ez az a nézet, ahol egy eltérés megkereshető: ha a
 * dobozban nem annyi pénz van, mint amennyit a rendszer mond, akkor itt kell
 * végigmenni, hol csúszott el.
 *
 * Ugyanaz a szerepe, mint a Notion "KP forgalom" adatbázisának, csak nem külön
 * kézzel vezetve: a sorok a kiadásokból és a bevételekből állnak össze, tehát
 * nem tud elcsúszni attól, amit a Pénzügyeken felvezettek.
 *
 * A számokat a szerver adja (lásd backend routes/finance.kp_naplo), ugyanabból
 * a szabályból, mint a kassza-kártya - így a két felület nem mondhat mást. */
export default async function KpForgalomPage() {
  const naplo = await getKpNaplo();
  const sorok = naplo?.sorok ?? [];

  // A táblázat a LEGFRISSEBBEL kezd: a napi munkában a legutóbbi mozgás a
  // kérdés. A futó egyenleg ettől még időrendi - a szerver a sorhoz számolta,
  // nem a megjelenítés sorrendjéhez.
  const megjelenitett = [...sorok]
    .reverse()
    // A DataTable egyedi id-t vár; a forrás-azonosítók viszont ütközhetnek
    // (egy kiadás és egy bevétel is lehet #12), ezért kapnak sorszámot.
    .map((sor, index) => ({ ...sor, id: index, forrasId: sor.id }));

  type Sor = (typeof megjelenitett)[number];

  const FORRAS_CIMKE: Record<string, string> = {
    kiadas: "Kiadás",
    bevetel: "Bevétel",
    kp_forgalom: "KP forgalom (Notion)",
  };

  const oszlopok: Column<Sor>[] = [
    {
      header: "Dátum",
      render: (s) => s.datum ?? "–",
      sortAccessor: (s) => s.datum,
    },
    {
      header: "Megnevezés",
      render: (s) => s.megnevezes,
      sortAccessor: (s) => s.megnevezes,
    },
    {
      header: "Típus",
      render: (s) => (
        <StatusBadge
          label={FORRAS_CIMKE[s.forras] ?? s.forras}
          tone={s.forras === "bevetel" ? "teal" : s.forras === "kiadas" ? "orange" : "neutral"}
        />
      ),
      sortAccessor: (s) => s.forras,
    },
    {
      header: "Projektkód",
      render: (s) => s.projektkod ?? "–",
      sortAccessor: (s) => s.projektkod,
    },
    {
      header: "Be",
      align: "right",
      render: (s) => (s.be > 0 ? <span className="text-text-teal">{formatHuf(s.be)}</span> : "–"),
      sortAccessor: (s) => s.be,
    },
    {
      header: "Ki",
      align: "right",
      render: (s) => (s.ki > 0 ? <span className="text-text-orange">{formatHuf(s.ki)}</span> : "–"),
      sortAccessor: (s) => s.ki,
    },
    {
      // A sor UTÁNI egyenleg - így ránézésre látszik, mikor merült ki (vagy
      // ment mínuszba) a kassza. A Notion-forgalom sorokon nincs: azok nem
      // mozgatják az egyenleget.
      header: "Egyenleg utána",
      align: "right",
      render: (s) =>
        s.egyenleg === null ? (
          <span className="text-text-muted">nem számít bele</span>
        ) : (
          <span className={s.egyenleg < 0 ? "text-text-danger" : undefined}>{formatHuf(s.egyenleg)}</span>
        ),
      sortAccessor: (s) => s.egyenleg,
    },
    {
      // Készpénzes kiadásnál a bizonylat a kérdés: számla nélkül a tétel a
      // könyvelésben nem elszámolható költség (lásd backend
      // services/bizonylat.py).
      header: "Számla",
      align: "right",
      render: (s) =>
        s.van_szamla === null ? (
          "–"
        ) : s.van_szamla ? (
          <StatusBadge label="Van" tone="success" />
        ) : (
          <StatusBadge label="Nincs" tone="warning" />
        ),
      sortAccessor: (s) => (s.van_szamla === null ? -1 : s.van_szamla ? 1 : 0),
    },
  ];

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="KP a kasszában"
            value={formatHuf(naplo?.egyenleg ?? 0)}
            icon={Wallet}
            tone={(naplo?.egyenleg ?? 0) < 0 ? "danger" : "accent"}
          />
          <StatCard label="Összes készpénz be" value={formatHuf(naplo?.osszes_be ?? 0)} icon={ArrowDownLeft} tone="teal" />
          <StatCard label="Összes készpénz ki" value={formatHuf(naplo?.osszes_ki ?? 0)} icon={ArrowUpRight} tone="orange" />
        </div>

        <Card title={`KP forgalom (${megjelenitett.length} mozgás)`}>
          <p className="mb-3 text-[12.5px] text-text-muted">
            Minden készpénzes bevétel és kiadás, időrendben. Az „Egyenleg utána" oszlop azt mondja meg, mennyi
            volt a kasszában az adott mozgás után – bruttóban, mert egy doboz pénz nem tud nettó lenni. Csak a
            MEGTÖRTÉNT mozgás szerepel: aminek nincs fizetési dátuma, az még nem hiányzik a kasszából.
          </p>

          {/* A Notionből örökölt KP forgalom sorok KÜLÖN kérdés: nagy részük
              egy kiadáshoz kötődik, tehát ugyanaz a pénzmozgás már ott van a
              kiadás soraként - beszámítva kétszer vonódna le. Ezt ki kell
              mondani, különben a lista úgy néz ki, mintha hiányos lenne. */}
          {naplo && naplo.kp_forgalom_kiadashoz_kotve + naplo.kp_forgalom_kotetlen > 0 && (
            <p className="mb-3 rounded-[var(--radius)] border border-border bg-surface-3 p-2.5 text-[12.5px] text-text-secondary">
              A listában szerepel {naplo.kp_forgalom_kiadashoz_kotve + naplo.kp_forgalom_kotetlen} sor a Notionből
              örökölt „KP forgalom" táblából ({formatHuf(naplo.kp_forgalom_be)} be,{" "}
              {formatHuf(naplo.kp_forgalom_ki)} ki), de ezek <strong>nem mozgatják az egyenleget</strong>:{" "}
              {naplo.kp_forgalom_kiadashoz_kotve} közülük egy konkrét kiadáshoz kötődik, tehát ugyanaz a
              pénzmozgás már szerepel a kiadás soraként – beszámítva kétszer vonódna le.
              {naplo.kp_forgalom_kotetlen > 0 && (
                <>
                  {" "}
                  További {naplo.kp_forgalom_kotetlen} sorról nem tudjuk, egy kiadás párja-e (a Notion-kapcsolat
                  hiányzik) – ezek addig maradnak ki, amíg ez el nem dől.
                </>
              )}
            </p>
          )}

          <DataTable<Sor>
            rows={megjelenitett}
            columns={oszlopok}
            emptyText="Még nincs egyetlen készpénzes mozgás sem – a Pénzügyeken a kiadás/bevétel fizetési módját kell Készpénzre állítani."
            getHref={(s) => s.href ?? ""}
            filterable
          />
        </Card>
      </div>
    </div>
  );
}
