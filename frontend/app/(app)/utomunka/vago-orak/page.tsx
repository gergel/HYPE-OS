import { redirect } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { getCurrentUser, getVagoOrak } from "@/lib/api";
import { szerepkorei } from "@/lib/permissions";

/** VÁGÓ-ÓRÁK - csak adminnak (a felhasználó kérése): melyik nap hány órát
 * töltött melyik vágó munkával, és a hónapban átlagosan napi hány órát -
 * CSAK a munkanapokat (hétfő-péntek) számolva. Az adat ugyanazokból a
 * munkaidő-mérésekből jön, mint a személy adatlapjának havi bontása. */
export default async function VagoOrakPage({
  searchParams,
}: {
  searchParams: Promise<{ ev?: string; honap?: string }>;
}) {
  const currentUser = await getCurrentUser();
  if (!szerepkorei(currentUser).includes("admin")) redirect("/nincs-jogosultsag");

  const params = await searchParams;
  const ma = new Date();
  const ev = Number(params.ev) || ma.getFullYear();
  const honap = Number(params.honap) || ma.getMonth() + 1;
  const adat = await getVagoOrak(ev, honap);

  const elozo = honap === 1 ? { ev: ev - 1, honap: 12 } : { ev, honap: honap - 1 };
  const kovetkezo = honap === 12 ? { ev: ev + 1, honap: 1 } : { ev, honap: honap + 1 };
  const honapNev = new Date(ev, honap - 1, 1).toLocaleDateString("hu-HU", { year: "numeric", month: "long" });

  // A hónap napjai, amin BÁRKI dolgozott - dátum szerint rendezve.
  const napok = Array.from(
    new Set((adat?.vagok ?? []).flatMap((v) => Object.keys(v.napi_percek))),
  ).sort();

  const ora = (perc: number) => `${(perc / 60).toLocaleString("hu-HU", { maximumFractionDigits: 1 })} ó`;
  const napFelirat = (iso: string) => {
    const d = new Date(`${iso}T12:00:00`);
    const hetvege = d.getDay() === 0 || d.getDay() === 6;
    return {
      szoveg: `${iso.slice(8, 10)}. (${d.toLocaleDateString("hu-HU", { weekday: "short" })})`,
      hetvege,
    };
  };

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        <div className="space-y-2">
          <BackLink href="/utomunka" label="Utómunka" />
          <h1 className="t-page">Vágó-órák</h1>
        </div>
        <Card
          title={honapNev}
          actions={
            <div className="flex items-center gap-2 text-[13px]">
              <a
                href={`/utomunka/vago-orak?ev=${elozo.ev}&honap=${elozo.honap}`}
                className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-text-secondary hover:bg-surface-3"
              >
                ← Előző hónap
              </a>
              <a
                href={`/utomunka/vago-orak?ev=${kovetkezo.ev}&honap=${kovetkezo.honap}`}
                className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-text-secondary hover:bg-surface-3"
              >
                Következő hónap →
              </a>
            </div>
          }
        >
          {!adat || adat.vagok.length === 0 ? (
            <p className="text-[13px] text-text-muted">Ebben a hónapban nincs rögzített vágási munkaidő.</p>
          ) : (
            <>
              <p className="mb-3 text-[12.5px] text-text-secondary">
                {adat.munkanapok} munkanap (hétfő–péntek{ev === ma.getFullYear() && honap === ma.getMonth() + 1 ? ", a mai napig" : ""}) – az
                átlag ezzel osztva számol, a hétvégi munka az összesbe beleszámít.
              </p>
              <div className="overflow-x-auto">
                <table className="os-table min-w-full border-collapse text-[13px]">
                  <thead>
                    <tr className="border-b border-border text-left text-text-secondary">
                      <th className="py-1.5 pr-4 font-medium">Nap</th>
                      {adat.vagok.map((v) => (
                        <th key={v.employee_id} className="py-1.5 pr-4 text-right font-medium">
                          <a href={`/csapat/${v.employee_id}`} className="text-text-accent hover:underline">
                            {v.full_name}
                          </a>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {napok.map((nap) => {
                      const f = napFelirat(nap);
                      return (
                        <tr key={nap} className="border-b border-border/60">
                          <td className={`py-1.5 pr-4 whitespace-nowrap ${f.hetvege ? "text-text-warning" : "text-text-primary"}`}>
                            {f.szoveg}
                          </td>
                          {adat.vagok.map((v) => (
                            <td key={v.employee_id} className="py-1.5 pr-4 text-right text-text-secondary">
                              {v.napi_percek[nap] ? ora(v.napi_percek[nap]) : "–"}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                    <tr className="border-b border-border font-medium">
                      <td className="py-2 pr-4 text-text-primary">Összesen</td>
                      {adat.vagok.map((v) => (
                        <td key={v.employee_id} className="py-2 pr-4 text-right text-text-primary">
                          {ora(v.osszes_perc)}
                        </td>
                      ))}
                    </tr>
                    <tr className="font-medium">
                      <td className="py-2 pr-4 text-text-primary">Átlag / munkanap</td>
                      {adat.vagok.map((v) => (
                        <td key={v.employee_id} className="py-2 pr-4 text-right text-text-accent">
                          {ora(v.atlag_perc_munkanap)}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
