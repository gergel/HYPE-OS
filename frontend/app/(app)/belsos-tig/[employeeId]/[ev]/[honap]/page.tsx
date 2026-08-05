import { notFound } from "next/navigation";
import Link from "next/link";
import { FileText, Wallet } from "lucide-react";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { formatDate, getHonapReszletek } from "@/lib/api";
import { formatHuf } from "@/lib/penz";

const ZAROLT = ["Kész", "Kiküldve", "Kihagyva"];

/** Egy belsős munkatárs EGY hónapja, saját oldalon: mennyi volt az alapbér,
 * mi került rá extraként (projektkódonként), mennyi a szumma, és hol tart a
 * hónap TIG-je.
 *
 * Azért önálló oldal és nem lenyíló doboz: egy elkészült hónapot utólag
 * gyakran egyedül kell megnyitni (könyvelés, kérdés a bérrel kapcsolatban) -
 * így megosztható linkje van, és nem kell hozzá végigscrollozni a munkatárs
 * teljes adatlapját. */
export default async function BelsosTigHonapPage({
  params,
}: {
  params: Promise<{ employeeId: string; ev: string; honap: string }>;
}) {
  const { employeeId, ev, honap } = await params;
  const adat = await getHonapReszletek(Number(employeeId), Number(ev), Number(honap));
  if (!adat) notFound();

  const record = adat.record;
  const zarolt = ZAROLT.includes(record?.allapot ?? "");
  const alapberTetel = adat.tetelek.find((t) => t.tipus === "alapber");
  // Az alapbér után az, ami hozzáadódik, végül ami levonódik - ugyanabban a
  // sorrendben, ahogy az összeg összeáll.
  const tobbiTetel = adat.tetelek.filter((t) => t.tipus !== "alapber");

  // A TIG dátumai: a dokumentumé (teljesítés, keltezés) és a számláé (meddig
  // kell fizetni, mikor utaltuk el). Csak azt írjuk ki, amit tudunk.
  const datumok = (
    [
      ["Teljesítés", record?.teljesites_datuma],
      ["Keltezés", record?.keltezes],
      ["Fizetési határidő", record?.fizetesi_hatarido],
      ["Utalás dátuma", record?.utalas_datuma],
    ] as [string, string | null | undefined][]
  ).filter((par): par is [string, string] => Boolean(par[1]));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-8">
        <div className="space-y-2">
          <BackLink href={`/csapat/${adat.employee_id}`} label={adat.full_name} />
          <h1 className="t-page">
            {adat.full_name} – {adat.ev}. {adat.honap_nev}
          </h1>
          <div className="flex flex-wrap items-center gap-3 text-[13px] text-text-secondary">
            <span>Belsős TIG</span>
            <StatusBadge
              label={record?.allapot ?? "Nincs elkezdve"}
              tone={zarolt ? "success" : record ? "warning" : "neutral"}
            />
            {record?.file_url && (
              <a
                href={record.file_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-text-accent hover:underline"
              >
                Kiküldött TIG dokumentum
              </a>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Alapbér" value={formatHuf(adat.alapber)} icon={Wallet} />
          <StatCard label="Extrák összesen" value={formatHuf(adat.extra)} icon={Wallet} tone="orange" />
          <StatCard
            label="Levonások összesen"
            value={adat.levonas > 0 ? `− ${formatHuf(adat.levonas)}` : formatHuf(0)}
            icon={Wallet}
            tone={adat.levonas > 0 ? "danger" : "default"}
          />
          <StatCard label="Havi szumma" value={formatHuf(adat.osszesen)} icon={Wallet} tone="accent" />
        </div>

        <Card title="A hónap tételei" icon={Wallet}>
          {adat.tetelek.length === 0 ? (
            <p className="text-[13px] text-text-muted">
              Ehhez a hónaphoz nincsenek tételek rögzítve.
              {record?.netto_osszeg != null && (
                <> A TIG-en rögzített összeg: {formatHuf(record.netto_osszeg)}.</>
              )}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="os-table w-full border-collapse text-[13px]">
                <thead>
                  <tr>
                    <th className="text-left">Tétel</th>
                    <th className="text-left">Projektkód</th>
                    <th className="text-left">Dátum</th>
                    <th className="text-right">Összeg</th>
                  </tr>
                </thead>
                <tbody>
                  {alapberTetel && (
                    <tr>
                      <td>
                        {alapberTetel.megnevezes}
                        <span className="ml-2 align-middle">
                          <StatusBadge label="Alapbér" tone="neutral" />
                        </span>
                      </td>
                      <td className="text-text-muted">–</td>
                      <td className="text-text-muted">{formatDate(alapberTetel.datum)}</td>
                      <td className="text-right tabular-nums">{formatHuf(alapberTetel.osszeg)}</td>
                    </tr>
                  )}
                  {tobbiTetel.map((t) => (
                    <tr key={t.id}>
                      <td>
                        {t.megnevezes}
                        {t.tipus === "levonando" && (
                          <span className="ml-2 align-middle">
                            <StatusBadge label="Levonandó" tone="danger" />
                          </span>
                        )}
                      </td>
                      <td>{t.projektkod ?? <span className="text-text-muted">Nincs projektkódhoz kötve</span>}</td>
                      <td className="text-text-muted">{formatDate(t.datum)}</td>
                      <td
                        className={`text-right tabular-nums ${
                          t.tipus === "levonando" ? "text-text-danger" : ""
                        }`}
                      >
                        {t.tipus === "levonando" ? `− ${formatHuf(t.osszeg)}` : formatHuf(t.osszeg)}
                      </td>
                    </tr>
                  ))}
                  {/* A szumma ugyanabban a táblában, hogy az összeadás
                      egyértelmű legyen - ne kelljen máshova nézni érte. */}
                  <tr>
                    <td className="font-medium text-text-primary" colSpan={3}>
                      Összesen
                    </td>
                    <td className="text-right font-medium tabular-nums text-text-primary">
                      {formatHuf(adat.osszesen)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
          {record?.plusz_afa && record.brutto_osszeg != null && (
            <p className="mt-4 text-[12.5px] text-text-muted">
              Plusz ÁFA-val: <span className="text-text-secondary">{formatHuf(record.brutto_osszeg)}</span>
            </p>
          )}
          {!zarolt && (
            <p className="mt-4 text-[12.5px] text-text-muted">
              A tételek a{" "}
              <Link href={`/csapat/${adat.employee_id}`} className="text-text-accent hover:underline">
                munkatárs adatlapján
              </Link>{" "}
              szerkeszthetők.
            </p>
          )}
        </Card>

        {record && (record.invoices.length > 0 || record.megjegyzes || datumok.length > 0) && (
          <Card title="A TIG-hez tartozó adatok" icon={FileText}>
            {record.megjegyzes && <p className="mb-4 text-[13px] text-text-secondary">{record.megjegyzes}</p>}
            {datumok.length > 0 && (
              <dl className="mb-5 grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2 xl:grid-cols-4">
                {datumok.map(([cimke, ertek]) => (
                  <div key={cimke}>
                    <dt className="t-label mb-1">{cimke}</dt>
                    <dd className="text-[13px] text-text-primary">{formatDate(ertek)}</dd>
                  </div>
                ))}
              </dl>
            )}
            {record.invoices.length > 0 && (
              <>
                <p className="t-label mb-2">Feltöltött számlák</p>
                <ul className="space-y-1.5">
                  {record.invoices.map((szamla) => (
                    <li key={szamla.id} className="text-[13px]">
                      <a
                        href={szamla.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-text-accent hover:underline"
                      >
                        {szamla.filename}
                      </a>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </Card>
        )}
      </div>
    </div>
  );
}
