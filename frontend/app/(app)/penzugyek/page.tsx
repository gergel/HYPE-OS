import { AlertCircle, Coins, Landmark, TrendingDown, TrendingUp } from "lucide-react";
import { formatHuf, getFinanceSummary, getUtalasraVaro } from "@/lib/api";
import { Card } from "@/components/Card";
import { BevetelekKartya } from "@/components/finance/BevetelekKartya";
import { FinanceMonthlyChart, KasszaWidget } from "@/components/finance/FinanceSummaryWidgets";
import { KiadasokKartya } from "@/components/finance/KiadasokKartya";
import { datumParam } from "@/components/finance/listaSegedek";
import { ProjektKintlevosegek } from "@/components/finance/ProjektKintlevosegek";
import { SzamlaCsomagLetoltes } from "@/components/finance/SzamlaCsomagLetoltes";
import { UtalasraVaroSzamlak } from "@/components/finance/UtalasraVaroSzamlak";
import { StatCard } from "@/components/StatCard";
import { TopBar } from "@/components/TopBar";

export default async function PenzugyekPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const kiadasTol = datumParam(sp.kiadas_tol);
  const kiadasIg = datumParam(sp.kiadas_ig);
  const bevetelTol = datumParam(sp.bevetel_tol);
  const bevetelIg = datumParam(sp.bevetel_ig);
  const [summary, utalasraVaro] = await Promise.all([getFinanceSummary(), getUtalasraVaro()]);

  // A Kiadások és a Bevételek listája külön komponens (a felhasználó kérése:
  // saját oldaluk is van, a gyorsabb elérés miatt - lásd /penzugyek/kiadasok
  // és /penzugyek/bevetelek); itt ugyanaz a kettő jelenik meg.
  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        {summary && (
          <>
            {/* A nagy számok NETTÓBAN vannak - bevételnél és kiadásnál
                egyaránt (lásd backend services/elszamolas.py). Az ÁFA átfolyó
                tétel: ha az egyik oldalt bruttóban, a másikat nettóban
                néznénk, a "profit" az ÁFA-tartalmak különbségével csúszna el.
                A bruttó ettől még ott van, halványan a szám alatt: az megy ki
                (és jön be) a bankszámlán. */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
              <StatCard
                label="Bevétel (idén, nettó)"
                value={formatHuf(summary.ytd_bevetel)}
                megjegyzes={`Bruttó: ${formatHuf(summary.ytd_bevetel_brutto)}`}
                icon={TrendingUp}
                tone="teal"
              />
              <StatCard
                label="Kiadás (idén, nettó)"
                value={formatHuf(summary.ytd_kiadas)}
                megjegyzes={`Bruttó: ${formatHuf(summary.ytd_kiadas_brutto)}`}
                icon={TrendingDown}
                tone="orange"
              />
              {/* A régi "Profit (idén)" helyén KÉT egyenleg: a kassza (KP
                  forgalom, 2026.01.01 óta - a régebbi sorok nem számítanak)
                  és a bankszámla idei mozgása. A KP BRUTTÓ (egy doboz pénz
                  nem tud nettó lenni), a számla NETTÓ - mint az éves
                  bevétel/kiadás, hogy az ÁFA ne torzítsa. */}
              <StatCard
                label="KP egyenleg"
                value={formatHuf(summary.kp_egyenleg)}
                megjegyzes="Házipénztár (bruttó)"
                icon={Coins}
                href="/penzugyek/kp-forgalom"
                tone={summary.kp_egyenleg >= 0 ? "accent" : "danger"}
              />
              <StatCard
                label="Számla egyenleg (idén, nettó)"
                value={formatHuf(summary.szamla_egyenleg)}
                megjegyzes={`Be: ${formatHuf(summary.szamla_be)} · ki: ${formatHuf(summary.szamla_ki)}${
                  summary.szamla_atvezetes ? ` (ebből kasszába: ${formatHuf(summary.szamla_atvezetes)})` : ""
                }`}
                icon={Landmark}
                tone={summary.szamla_egyenleg >= 0 ? "accent" : "danger"}
              />
              <StatCard
                label={`Kintlévőség (${summary.kintlevo_projektek_szama} projekt, nettó)`}
                value={formatHuf(summary.osszes_kintlevoseg)}
                megjegyzes={`Számlázandó: ${summary.szamlazando_db} · kint lévő számla: ${summary.szamla_kint_db}${
                  summary.lejart_db ? ` (${summary.lejart_db} lejárt)` : ""
                }`}
                icon={AlertCircle}
                tone={summary.osszes_kintlevoseg > 0 ? "pink" : "blue"}
              />
            </div>

            {/* PROJEKT-KINTLÉVŐSÉGEK: MINDEN projektkód, amiért még nem jött
                meg a pénz (számlával vagy anélkül) - a pénzügyes innen látja,
                hová kell még számlát kiállítani, és mi van kint kifizetetlenül
                (lásd backend services/kintlevoseg.py). */}
            <Card title="Projekt kintlévőségek">
              <ProjektKintlevosegek summary={summary} />
            </Card>

            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              <Card title="Bevétel / kiadás - utolsó 12 hónap (nettó)">
                <FinanceMonthlyChart trend={summary.havi_trend} />
              </Card>
              {/* MENNYI KÉSZPÉNZ VAN A KASSZÁBAN - a készpénzesnek jelölt
                  bevételek és kiadások különbsége (lásd backend
                  services/fizetesi_mod.py). */}
              <Card title="Házipénztár">
                <KasszaWidget kassza={summary.kassza} />
              </Card>

            {summary.ytd_kiadas_fizetesi_mod_szerint.length > 0 && (
              <Card title="Kiadás fizetési mód szerint (idén, nettó)">
                <ul className="divide-y divide-border">
                  {summary.ytd_kiadas_fizetesi_mod_szerint.map((row) => (
                    <li key={row.kifizetes_modja ?? "ismeretlen"} className="flex items-center justify-between py-2 text-[13px]">
                      <span className="text-text-secondary">{row.kifizetes_modja ?? "Nincs megadva"}</span>
                      <span className="font-medium text-text-primary">{formatHuf(row.osszeg)}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            </div>
          </>
        )}

        {/* Ami már megérkezett számlaként, de még nem utaltuk el - egy
            listában a három forrásból (kiadás, külsős és belsős TIG), a
            kijelöltek számlái egyben letölthetők. */}
        <Card title={`Utalásra váró számlák (${utalasraVaro.length})`}>
          <UtalasraVaroSzamlak kezdeti={utalasraVaro} />
        </Card>

        {/* Havi számla-csomag a könyvelésnek - egy hónap összes bejövő és
            kimenő számlája egyetlen ZIP-ben. */}
        <Card title="Havi számlák letöltése">
          <SzamlaCsomagLetoltes />
        </Card>

        <KiadasokKartya tol={kiadasTol} ig={kiadasIg} nezet={sp.kiadas_nezet === "varo" ? "varo" : "kifizetett"} />

        <BevetelekKartya tol={bevetelTol} ig={bevetelIg} />
      </div>
    </div>
  );
}
