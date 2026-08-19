import { getKrumpelloKiadasok, type KrumpelloForras } from "@/lib/api";
import { KrumpelloFejlec } from "@/components/krumpello/KrumpelloFejlec";
import { KiadasSzerkeszto } from "@/components/krumpello/KiadasSzerkeszto";
import { PapirFeltoltes } from "@/components/kotelezettseg/PapirFeltoltes";
import { formatFt } from "@/lib/ido";

export const metadata = { title: "Krumpello – Kiadás" };

/** A három kiadás-forrás. Nem könyvelési finomság: külön egyenlegük van, és az
 * "extra" (számla nélküli) külön kérdés, nem a másik kettő egy változata. */
const FORRASOK: { kulcs: KrumpelloForras; cimke: string; leiras: string }[] = [
  { kulcs: "utalas", cimke: "Utalás / bankkártya", leiras: "A bankszámláról ment ki." },
  { kulcs: "keszpenz", cimke: "Készpénz", leiras: "A kasszából ment ki." },
  { kulcs: "extra", cimke: "Extra – nincs hozzá számla", leiras: "Nincs számla, ami megmagyarázná, hova ment." },
];

export default async function KrumpelloKiadasPage({
  searchParams,
}: {
  searchParams: Promise<{ tol?: string; ig?: string }>;
}) {
  const { tol, ig } = await searchParams;
  const kiadasok = await getKrumpelloKiadasok(tol, ig);

  return (
    <>
      <KrumpelloFejlec
        cim="Kiadás"
        leiras="Forrás szerint bontva – az „extra” az, amihez nincs számla."
        tol={tol}
        ig={ig}
        utvonal="/krumpello/kiadas"
        jobbOldal={<KiadasSzerkeszto />}
      />
      <div className="space-y-8 p-8">
        {FORRASOK.map(({ kulcs, cimke, leiras }) => {
          const sajat = kiadasok.filter((k) => k.forras === kulcs);
          const brutto = sajat.reduce((s, k) => s + (k.brutto ?? 0), 0);
          const afa = sajat.reduce((s, k) => s + (k.afa ?? 0), 0);
          return (
            <section key={kulcs}>
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
                <div>
                  <h2 className={`t-section ${kulcs === "extra" ? "!text-[color:var(--text-accent)]" : ""}`}>{cimke}</h2>
                  <p className="mt-0.5 text-[12px] text-text-muted">{leiras}</p>
                </div>
                <div className="text-right">
                  <p className="text-[19px] font-semibold tabular-nums text-text-primary">{formatFt(brutto)}</p>
                  <p className="text-[11.5px] text-text-muted">
                    {sajat.length} tétel{kulcs !== "extra" && ` · ebből ÁFA ${formatFt(afa)}`}
                  </p>
                </div>
              </div>

              {sajat.length === 0 ? (
                <p className="text-[13px] text-text-muted">Erre az időszakra nincs ilyen tétel.</p>
              ) : (
                <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border bg-surface-2">
                  <table className="w-full border-collapse text-[13px]">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="px-4 py-2 text-left font-medium text-text-muted">Kedvezményezett</th>
                        <th className="px-4 py-2 text-left font-medium text-text-muted">Dátum</th>
                        <th className="px-4 py-2 text-left font-medium text-text-muted">Tétel neve</th>
                        {kulcs !== "extra" && (
                          <>
                            <th className="px-4 py-2 text-right font-medium text-text-muted">Nettó</th>
                            <th className="px-4 py-2 text-right font-medium text-text-muted">ÁFA</th>
                          </>
                        )}
                        <th className="px-4 py-2 text-right font-medium text-text-muted">
                          {kulcs === "extra" ? "Összeg" : "Bruttó"}
                        </th>
                        {/* A számla feltöltése SEHOL nem kötelező - az
                            "extra" tételnek épp az a definíciója, hogy nincs
                            hozzá papír. A lehetőség viszont ott is kell:
                            néha utólag előkerül a blokk. */}
                        <th className="px-4 py-2 text-left font-medium text-text-muted">Számla / blokk</th>
                        <th className="px-4 py-2" />
                      </tr>
                    </thead>
                    <tbody>
                      {sajat.map((k) => (
                        <tr key={k.id} className="border-b border-border last:border-0">
                          <td className="px-4 py-2.5 text-text-primary">{k.kedvezmenyezett}</td>
                          <td className="whitespace-nowrap px-4 py-2.5 text-text-secondary">
                            {/* A dátum nélküli tétel nem hiba, hanem "még nem
                                azonosítottuk be" - ezért kiírjuk, nem elrejtjük. */}
                            {k.datum ?? <span className="text-text-muted">nincs dátum</span>}
                          </td>
                          <td className="px-4 py-2.5 text-text-secondary">{k.megnevezes ?? "–"}</td>
                          {kulcs !== "extra" && (
                            <>
                              <td className="px-4 py-2.5 text-right tabular-nums text-text-secondary">
                                {k.netto != null ? formatFt(k.netto) : "–"}
                              </td>
                              <td className="px-4 py-2.5 text-right tabular-nums text-text-secondary">
                                {k.afa != null ? formatFt(k.afa) : "–"}
                              </td>
                            </>
                          )}
                          <td className="whitespace-nowrap px-4 py-2.5 text-right font-medium tabular-nums text-text-primary">
                            {k.brutto != null ? formatFt(k.brutto) : "–"}
                          </td>
                          <td className="px-4 py-2.5">
                            <PapirFeltoltes
                              entityType="krumpelloKiadas"
                              entityId={k.id}
                              kategoria="szamla"
                              canEdit
                              canDelete
                              kezdeti={k.csatolmanyok}
                              uresSzoveg=""
                              gombCimke="+ Számla"
                            />
                          </td>
                          <td className="px-4 py-2.5 text-right align-top">
                            <KiadasSzerkeszto kiadas={k} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          );
        })}
      </div>
    </>
  );
}
