import { getKrumpelloNapok } from "@/lib/api";
import { KrumpelloFejlec } from "@/components/krumpello/KrumpelloFejlec";
import { NapSzerkeszto } from "@/components/krumpello/NapSzerkeszto";
import { PapirFeltoltes } from "@/components/kotelezettseg/PapirFeltoltes";
import { formatFt } from "@/lib/ido";

export const metadata = { title: "Krumpello – Bevétel" };

/** Napi kassza-zárások.
 *
 * Naponta egy sor - a bevitel ezért "nap kiválasztása és kitöltése", nem "új
 * rekord": ha az adott napra már van zárás, azt írja felül (lásd backend
 * upsert_nap). Így egy elrontott nap javítása ugyanaz a mozdulat, mint a
 * rögzítése, és nem keletkezhet két zárás ugyanarra a napra. */
export default async function KrumpelloBevetelPage({
  searchParams,
}: {
  searchParams: Promise<{ tol?: string; ig?: string }>;
}) {
  const { tol, ig } = await searchParams;
  const napok = await getKrumpelloNapok(tol, ig);

  const osszeg = (kivalaszt: (n: (typeof napok)[number]) => number | null) =>
    napok.reduce((s, n) => s + (kivalaszt(n) ?? 0), 0);

  return (
    <>
      <KrumpelloFejlec
        cim="Bevétel"
        leiras="Napi kassza-zárás. Egy naphoz egy sor tartozik – az újbóli mentés felülírja."
        tol={tol}
        ig={ig}
        utvonal="/krumpello/bevetel"
        jobbOldal={<NapSzerkeszto />}
      />
      <div className="p-8">
        <div className="mb-5 flex flex-wrap gap-8 rounded-[var(--radius-lg)] border border-border bg-surface-2 px-6 py-4">
          <Osszesen cimke="Bruttó" ertek={osszeg((n) => n.brutto_osszesen)} />
          <Osszesen cimke="Nettó" ertek={osszeg((n) => n.netto_osszesen)} />
          <Osszesen cimke="Borravaló" ertek={osszeg((n) => n.borravalo_osszesen)} />
          <Osszesen cimke="Extra (számla nélkül)" ertek={osszeg((n) => n.extra)} kiemelt />
          <Osszesen cimke="Napok" ertek={napok.length} nyers />
        </div>

        {napok.length === 0 ? (
          <p className="text-[13px] text-text-muted">
            Erre az időszakra nincs rögzített nap. Az „Új nap rögzítése” gombbal vihetsz fel egyet.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border bg-surface-2">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border">
                  <Fej>Dátum</Fej>
                  <Fej jobbra>Bruttó KP</Fej>
                  <Fej jobbra>Bruttó kártya</Fej>
                  <Fej jobbra>Bruttó összesen</Fej>
                  <Fej jobbra>Nettó összesen</Fej>
                  <Fej jobbra>Borravaló</Fej>
                  <Fej jobbra>Extra</Fej>
                  <Fej>Megjegyzés</Fej>
                  {/* A napi zárás bizonylata (pénztárgép-napi jelentés,
                      terminál-összesítő). Nem kötelező: a kassza a számoktól
                      kerek, a papír csak alátámasztja. */}
                  <Fej>Számla / bizonylat</Fej>
                  <Fej />
                </tr>
              </thead>
              <tbody>
                {napok.map((n) => (
                  <tr key={n.id} className="border-b border-border last:border-0">
                    <td className="whitespace-nowrap px-4 py-2.5 text-text-primary">{n.datum}</td>
                    <Szam ertek={n.brutto_kp} />
                    <Szam ertek={n.brutto_kartya} />
                    <Szam ertek={n.brutto_osszesen} eros />
                    <Szam ertek={n.netto_osszesen} />
                    <Szam ertek={n.borravalo_osszesen} />
                    <Szam ertek={n.extra} kiemelt />
                    <td className="px-4 py-2.5 text-text-muted">{n.megjegyzes ?? "–"}</td>
                    <td className="px-4 py-2.5">
                      <PapirFeltoltes
                        entityType="krumpelloNap"
                        entityId={n.id}
                        kategoria="szamla"
                        canEdit
                        canDelete
                        kezdeti={n.csatolmanyok}
                        uresSzoveg=""
                        gombCimke="+ Bizonylat"
                      />
                    </td>
                    <td className="px-4 py-2.5 text-right align-top">
                      <NapSzerkeszto nap={n} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

function Fej({ children, jobbra = false }: { children?: React.ReactNode; jobbra?: boolean }) {
  return (
    <th className={`px-4 py-2 font-medium text-text-muted ${jobbra ? "text-right" : "text-left"}`}>{children}</th>
  );
}

function Szam({ ertek, eros = false, kiemelt = false }: { ertek: number | null; eros?: boolean; kiemelt?: boolean }) {
  return (
    <td
      className={`whitespace-nowrap px-4 py-2.5 text-right tabular-nums ${
        kiemelt && ertek ? "text-text-accent" : eros ? "text-text-primary" : "text-text-secondary"
      }`}
    >
      {ertek ? formatFt(ertek) : "–"}
    </td>
  );
}

function Osszesen({
  cimke,
  ertek,
  kiemelt = false,
  nyers = false,
}: {
  cimke: string;
  ertek: number;
  kiemelt?: boolean;
  nyers?: boolean;
}) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-wide text-text-muted">{cimke}</p>
      <p className={`mt-0.5 text-[17px] font-semibold tabular-nums ${kiemelt ? "text-text-accent" : "text-text-primary"}`}>
        {nyers ? ertek : formatFt(ertek)}
      </p>
    </div>
  );
}
