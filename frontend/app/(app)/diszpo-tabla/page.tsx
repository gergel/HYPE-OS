import { notFound } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { DiszpoTablaRacs } from "@/components/DiszpoTablaRacs";
import { StatusBadge } from "@/components/StatusBadge";
import { HONAP_NEVEK } from "@/lib/diszpoSzin";
import {
  getDiszpoHaviAllas,
  getDiszpoMunkalap,
  getDiszpoMunkalapok,
  getEmployees,
  getMyPagePermissions,
  formatHuf,
} from "@/lib/api";

const PAGE = "/diszpo-tabla";

/** A HYPE 2026 táblázat - a Google Sheet munkalapjai a rendszerben.
 *
 * Ez a tábla nem csak beosztás volt: a CELLA SZÍNE hordozta a legfontosabb
 * adatot, azt, hogy ki melyik nap dolgozott. Ebből derül ki, hány munkanapja
 * van valakinek egy hónapban - és ez dönti el, mikor fogy el a szerződött
 * napjainak száma, vagyis mikortól kell a PLUSZ NAP díján számolni a
 * projektek önköltségébe (lásd backend services/munkanap_szamlalo.py).
 *
 * A munkalapok fülekként állnak egymás mellett, ahogy a Sheetben. */
export default async function DiszpoTablaPage({
  searchParams,
}: {
  searchParams: Promise<{ lap?: string; ev?: string; honap?: string }>;
}) {
  const { lap, ev, honap } = await searchParams;
  const [munkalapok, pagePermissions] = await Promise.all([getDiszpoMunkalapok(), getMyPagePermissions()]);

  if (munkalapok.length === 0) {
    return (
      <div className="flex flex-1 flex-col">
        <TopBar />
        <div className="flex-1 p-8">
          <Card title="HYPE 2026 tábla">
            <p className="text-[13px] text-text-secondary">
              A táblázat még nincs átvéve. A backend gépén futtatható:{" "}
              <code className="rounded bg-surface-3 px-1 py-0.5">
                python scripts/diszpo_tabla_import.py --vegrehajt
              </code>{" "}
              – ez hozza át a Google Sheet minden munkalapját, a cellák színével együtt.
            </p>
          </Card>
        </div>
      </div>
    );
  }

  const aktivId = lap ? Number(lap) : munkalapok[0].id;
  const aktiv = munkalapok.find((m) => m.id === aktivId);
  if (!aktiv) notFound();

  // MELYIK HÓNAP - a címben, tehát megosztható és könyvjelzőzhető. Alapból a
  // mai; a nyilakkal bármelyik másikra lehet lépni.
  const ma = new Date();
  const nezettEv = Number(ev) || ma.getFullYear();
  const nezettHonap = Math.min(Math.max(Number(honap) || ma.getMonth() + 1, 1), 12);
  const [munkalap, emberek, haviAllas] = await Promise.all([
    getDiszpoMunkalap(aktiv.id),
    getEmployees(),
    getDiszpoHaviAllas(nezettEv, nezettHonap),
  ]);
  if (!munkalap) notFound();

  const canEdit = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");
  // A sor/oszlop TÖRLÉSE külön jog: az a tartalmát is viszi, és egy 146
  // oszlopos munkalapon nem visszavonható egy kattintással.
  const canDelete = pagePermissions === null || !!pagePermissions[PAGE]?.includes("delete");
  // A NAPIDÍJ ÉS A PLUSZ NAPOK a Pénzügyek jogosultságához kötöttek: az
  // bér-adat, nem beosztás. A SZERVER dönti el, mit ad ki (lásd backend
  // routes/diszpo_tabla._lathatja_a_penzugyet) - itt csak azt kérdezzük meg,
  // megkaptuk-e, hogy ne rajzoljunk üres oszlopokat annak, aki úgysem látja.
  const latszikPenz = haviAllas.some((a) => a.penzugyi_adat);
  // Akinél a szerződött napszám elfogyott: innentől a plusz nap díján
  // számolunk a projektek önköltségébe.
  const elfogyott = haviAllas.filter((a) => a.plusz_napok.length > 0);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-8">
        <Card title="HYPE 2026 tábla">
          {/* A FÜLEK - ahogy a Sheetben, balról jobbra. */}
          <div className="mb-4 flex flex-wrap gap-1.5 border-b border-border pb-3">
            {munkalapok.map((m) => (
              <Link
                key={m.id}
                href={`/diszpo-tabla?lap=${m.id}`}
                className={`rounded-[var(--radius)] px-3 py-1.5 text-[13px] transition-colors ${
                  m.id === aktiv.id
                    ? "bg-bg-accent text-text-accent"
                    : "text-text-secondary hover:bg-surface-3"
                }`}
              >
                {m.nev}
              </Link>
            ))}
          </div>

          <DiszpoTablaRacs
            munkalap={munkalap}
            canEdit={canEdit}
            canDelete={canDelete}
            emberek={emberek.map((e) => ({ id: e.id, nev: e.full_name }))}
          />
        </Card>

        {/* A TÁBLÁZAT LÉNYEGE SZÁMOKBAN: ki hány napot dolgozott ebben a
            hónapban, és kinél fogyott el a szerződött napszám. */}
        <Card title={`Munkanapok – ${nezettEv}. ${HONAP_NEVEK[nezettHonap - 1]}`}>
          {/* HÓNAPLÉPTETŐ: bármelyik hónapra vissza lehet nézni, nem csak a
              mostanira. A választás a címben van, tehát megosztható. */}
          <div className="mb-3 flex flex-wrap items-center gap-1.5">
            {[-1, 1].map((irany) => {
              const d = new Date(nezettEv, nezettHonap - 1 + irany, 1);
              return (
                <Link
                  key={irany}
                  href={`/diszpo-tabla?lap=${aktiv.id}&ev=${d.getFullYear()}&honap=${d.getMonth() + 1}`}
                  className="rounded-[var(--radius)] border border-border px-2.5 py-1 text-[12.5px] text-text-secondary hover:bg-surface-3"
                >
                  {irany < 0 ? "← Előző" : "Következő →"}
                </Link>
              );
            })}
            <span className="ml-2 flex flex-wrap gap-1">
              {HONAP_NEVEK.map((nev, i) => (
                <Link
                  key={nev}
                  href={`/diszpo-tabla?lap=${aktiv.id}&ev=${nezettEv}&honap=${i + 1}`}
                  className={`rounded-[var(--radius)] px-2 py-1 text-[12px] ${
                    i + 1 === nezettHonap
                      ? "bg-bg-accent text-text-accent"
                      : "text-text-muted hover:bg-surface-3"
                  }`}
                >
                  {nev.slice(0, 3)}.
                </Link>
              ))}
            </span>
          </div>

          {haviAllas.length === 0 ? (
            <p className="text-[13px] text-text-secondary">
              Ebben a hónapban még nincs kiszínezett munkanap – vagy az oszlopok nincsenek munkatárshoz kötve. A
              kötés a táblázatban, az oszlop egy cellájára kattintva adható meg.
            </p>
          ) : (
            <>
              <p className="mb-3 text-[12.5px] text-text-secondary">
                Munkanapnak számít a <b>zöld</b>, a <b>kék</b> és az <b>üresen hagyott</b> nap is – az utóbbi azért,
                mert a napja le volt kötve, csak nem tudtunk rá munkát adni.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-[13px]">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Munkatárs</th>
                      <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Munkanap</th>
                      {latszikPenz && (
                        <>
                          <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Szerződve</th>
                          <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Mikor fogy el</th>
                          <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Napidíj</th>
                          <th className="py-1.5 text-right font-medium text-text-secondary">Plusz nap díja</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {haviAllas.map((a) => (
                      <tr key={a.employee_id} className="border-b border-border last:border-0">
                        <td className="py-2 pr-6 text-text-primary">{a.employee_nev ?? `#${a.employee_id}`}</td>
                        <td className="py-2 pr-6 text-right tabular-nums text-text-primary">{a.munkanapok}</td>
                        {latszikPenz && (
                        <>
                        <td className="py-2 pr-6 text-right tabular-nums text-text-secondary">
                          {a.szerzodott_napok ?? "–"}
                        </td>
                        <td className="py-2 pr-6">
                          {a.plusz_napok.length > 0 ? (
                            <span className="flex flex-wrap items-center gap-2">
                              <StatusBadge label={`${a.plusz_napok.length} plusz nap`} tone="warning" />
                              <span className="text-[12px] text-text-muted">
                                {a.hatarnap} után: {a.plusz_napok.join(", ")}
                              </span>
                            </span>
                          ) : a.szerzodott_napok ? (
                            <span className="text-text-muted">a kereten belül</span>
                          ) : (
                            <span className="text-text-muted">nincs megadva napszám</span>
                          )}
                        </td>
                        <td className="py-2 pr-6 text-right tabular-nums text-text-secondary">
                          {a.napi_dij != null ? formatHuf(a.napi_dij) : "–"}
                        </td>
                        <td className="py-2 text-right tabular-nums text-text-secondary">
                          {a.plusz_nap_napi_dij != null ? (
                            formatHuf(a.plusz_nap_napi_dij)
                          ) : (
                            <span className="text-text-muted" title="Enélkül a plusz nap is a rendes napidíjon számol">
                              nincs megadva
                            </span>
                          )}
                        </td>
                        </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {latszikPenz && elfogyott.length > 0 && (
                <p className="mt-3 text-[12.5px] text-text-secondary">
                  {elfogyott.length} munkatársnál elfogyott a havi szerződött napszám. A határnap utáni forgatásaikon
                  a <b>plusz nap napidíját</b> számoljuk a projekt önköltségébe – akinél az nincs megadva, ott marad a
                  rendes napidíj (a hiányzó adat nem árazhat át semmit csendben).
                </p>
              )}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
