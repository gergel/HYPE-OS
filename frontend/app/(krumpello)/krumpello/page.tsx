import { getKrumpelloOsszesito } from "@/lib/api";
import { KrumpelloFejlec } from "@/components/krumpello/KrumpelloFejlec";
import { formatFt } from "@/lib/ido";

export const metadata = { title: "Krumpello – Áttekintés" };

/** A Krumpello nyitóoldala: mi jött be, mi ment ki, és hol állunk.
 *
 * A három egyenleg MÁST mér, ezért külön kártyán van, nem egy összegben (lásd
 * backend services/krumpello_osszesito.py):
 *
 * - a SZÁMLA egyenleg a bankban lévő pénz,
 * - a KÉSZPÉNZ egyenleg a kasszában lévő - ez fizikailag megszámolható,
 * - az EXTRA egyenleg a SZÁMLA NÉLKÜLI mozgásoké: ez az egyetlen szám, ami
 *   megmondja, hogy az elszámolatlan pénz pluszban vagy mínuszban áll.
 */
export default async function KrumpelloAttekintesPage({
  searchParams,
}: {
  searchParams: Promise<{ tol?: string; ig?: string }>;
}) {
  const { tol, ig } = await searchParams;
  const o = await getKrumpelloOsszesito(tol, ig);

  return (
    <>
      <KrumpelloFejlec
        cim="Áttekintés"
        leiras="A Krumpello saját kasszája – a HYPE pénzügyeitől teljesen elkülönítve."
        tol={tol}
        ig={ig}
        utvonal="/krumpello"
      />
      <div className="p-8">
        {o === null ? (
          <p className="text-[13px] text-text-danger">
            Nem sikerült betölteni az összesítőt. Ellenőrizd, hogy van-e jogosultságod a Krumpellóhoz.
          </p>
        ) : (
          <div className="space-y-6">
            {/* Az EXTRA a legfelső helyen: ez az, amit naponta nézni kell. */}
            <ExtraKartya bevetel={o.extra_bevetel} kiadas={o.kiadas_extra} egyenleg={o.extra_egyenleg} />

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Mutato cimke="Bruttó bevétel" ertek={o.bevetel.brutto} reszlet={`KP ${formatFt(o.bevetel.brutto_kp)} · Kártya ${formatFt(o.bevetel.brutto_kartya)}`} />
              <Mutato cimke="Kiadás – utalás" ertek={-o.kiadas_utalas.brutto} reszlet={`ebből ÁFA ${formatFt(o.kiadas_utalas.afa)}`} />
              <Mutato cimke="Kiadás – készpénz" ertek={-o.kiadas_keszpenz.brutto} reszlet={`ebből ÁFA ${formatFt(o.kiadas_keszpenz.afa)}`} />
              <Mutato cimke="Borravaló" ertek={o.bevetel.borravalo} reszlet="A dolgozóké – nem árbevétel" semleges />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <EgyenlegKartya
                cim="Számla egyenleg"
                magyarazat="Kártyás bevétel mínusz a bankból indított utalások."
                netto={o.szamla_egyenleg_netto}
                brutto={o.szamla_egyenleg_brutto}
              />
              <EgyenlegKartya
                cim="Készpénz egyenleg"
                magyarazat="Készpénzes bevétel mínusz a készpénzes kiadás – ennyi kell hogy legyen a kasszában."
                netto={o.keszpenz_egyenleg_netto}
                brutto={o.keszpenz_egyenleg_brutto}
              />
            </div>

            <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6">
              <p className="t-card mb-3">Munkabér</p>
              <div className="flex flex-wrap gap-8">
                <Adat cimke="Ledolgozott óra" ertek={`${o.munkaora.toLocaleString("hu-HU")} óra`} />
                <Adat cimke="Bér összesen" ertek={formatFt(o.munkaber)} />
                {/* A "még jár" az egyetlen szám itt, ami TEENDŐ - ezért kap
                    figyelmeztető színt, amíg nem nulla. */}
                <Adat
                  cimke="Még jár"
                  ertek={o.munkaber_hatralek ? formatFt(o.munkaber_hatralek) : "rendezve"}
                  veszely={o.munkaber_hatralek > 0}
                />
                <Adat cimke="Borravaló" ertek={formatFt(o.munkaber_borravalo)} />
                <Adat
                  cimke="Átlagos órabér"
                  ertek={o.munkaora > 0 ? formatFt(Math.round(o.munkaber / o.munkaora)) : "–"}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

/** Az extra (számla nélküli) mozgások - a modul kulcskérdése.
 *
 * Azért kap kiemelt, egész széles kártyát, mert a többi szám könyvelésből
 * úgyis kijön; EZ az, amit csak itt lehet látni. */
function ExtraKartya({ bevetel, kiadas, egyenleg }: { bevetel: number; kiadas: number; egyenleg: number }) {
  const pluszban = egyenleg >= 0;
  return (
    <div
      className={`rounded-[var(--radius-lg)] border p-6 ${
        pluszban ? "border-[color:var(--text-success)]/35 bg-bg-success" : "border-[color:var(--text-danger)]/35 bg-bg-danger"
      }`}
    >
      <p className="text-[11px] font-medium uppercase tracking-wide text-text-muted">
        Extra – amihez nincs számla
      </p>
      <p className={`mt-1 text-[34px] font-semibold leading-tight ${pluszban ? "text-text-success" : "text-text-danger"}`}>
        {egyenleg > 0 ? "+" : ""}
        {formatFt(egyenleg)}
      </p>
      <p className="mt-1 text-[13px] text-text-secondary">
        {pluszban
          ? "Több számlázatlan pénz jött be, mint amennyi kiment."
          : "Több számlázatlan pénz ment ki, mint amennyi bejött."}
      </p>
      <div className="mt-4 flex flex-wrap gap-8 border-t border-border pt-4">
        <Adat cimke="Extra bevétel" ertek={formatFt(bevetel)} />
        <Adat cimke="Extra kiadás" ertek={formatFt(kiadas)} />
      </div>
    </div>
  );
}

function Mutato({
  cimke,
  ertek,
  reszlet,
  semleges = false,
}: {
  cimke: string;
  ertek: number;
  reszlet?: string;
  /** Olyan összeg, aminek nincs "jó/rossz" iránya (pl. borravaló). */
  semleges?: boolean;
}) {
  const szin = semleges ? "text-text-primary" : ertek < 0 ? "text-text-danger" : "text-text-primary";
  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-5">
      <p className="text-[11px] font-medium uppercase tracking-wide text-text-muted">{cimke}</p>
      <p className={`mt-1 text-[21px] font-semibold tabular-nums ${szin}`}>{formatFt(ertek)}</p>
      {reszlet && <p className="mt-1 text-[11.5px] text-text-muted">{reszlet}</p>}
    </div>
  );
}

function EgyenlegKartya({
  cim,
  magyarazat,
  netto,
  brutto,
}: {
  cim: string;
  magyarazat: string;
  netto: number;
  brutto: number;
}) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-6">
      <p className="t-card">{cim}</p>
      <p className="mt-1 text-[12px] text-text-muted">{magyarazat}</p>
      <div className="mt-4 flex flex-wrap gap-8">
        <Adat cimke="Bruttó" ertek={formatFt(brutto)} veszely={brutto < 0} nagy />
        <Adat cimke="Nettó" ertek={formatFt(netto)} veszely={netto < 0} />
      </div>
    </div>
  );
}

function Adat({
  cimke,
  ertek,
  veszely = false,
  nagy = false,
}: {
  cimke: string;
  ertek: string;
  veszely?: boolean;
  nagy?: boolean;
}) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-wide text-text-muted">{cimke}</p>
      <p
        className={`mt-0.5 font-semibold tabular-nums ${nagy ? "text-[21px]" : "text-[16px]"} ${
          veszely ? "text-text-danger" : "text-text-primary"
        }`}
      >
        {ertek}
      </p>
    </div>
  );
}
