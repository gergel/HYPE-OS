import {
  getCurrentUser,
  getKrumpelloDolgozok,
  getKrumpelloIdoszakok,
  getKrumpelloMunkaorak,
  getMyPagePermissions,
  krumpelloBejelentesCimke,
} from "@/lib/api";
import { canDoAction } from "@/lib/permissions";
import { IdoszakKezelo } from "@/components/krumpello/IdoszakKezelo";
import { KrumpelloFejlec } from "@/components/krumpello/KrumpelloFejlec";
import { MunkaoraSzerkeszto } from "@/components/krumpello/MunkaoraSzerkeszto";
import { IdoszakKifizetes, KifizetesKapcsolo } from "@/components/krumpello/KifizetesKapcsolo";
import { formatFt } from "@/lib/ido";

export const metadata = { title: "Krumpello – Munkabér" };

/** Munkabér-elszámolás: ki, mikor, hány órát, milyen órabéren.
 *
 * Két nézet egy oldalon, mert két külön kérdés van:
 *
 * 1. "Kinek mennyit kell fizetnem?" - emberenkénti összesítés, ez a felső rész.
 * 2. "Ez a szám miből jött ki?" - naplószerű sorlista, ez az alsó.
 *
 * Külön oldalra bontva a második mindig egy kattintásra lenne az elsőtől, és
 * pont a kifizetés pillanatában kellene odalapozni. */
export default async function KrumpelloMunkaberPage({
  searchParams,
}: {
  searchParams: Promise<{ tol?: string; ig?: string }>;
}) {
  const { tol, ig } = await searchParams;
  const [dolgozok, orak, idoszakok, currentUser, pagePermissions] = await Promise.all([
    getKrumpelloDolgozok(tol, ig),
    getKrumpelloMunkaorak(tol, ig),
    getKrumpelloIdoszakok(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const canEdit = canDoAction(currentUser, pagePermissions, "/krumpello", "edit");

  const dolgozokOraval = dolgozok.filter((d) => d.ora_osszesen > 0 || d.aktiv);
  const berOsszesen = dolgozok.reduce((s, d) => s + d.fizetes_osszesen, 0);
  const oraOsszesen = dolgozok.reduce((s, d) => s + d.ora_osszesen, 0);
  const borravaloOsszesen = dolgozok.reduce((s, d) => s + d.borravalo_osszesen, 0);
  // A "még jár" a nap végén az egyetlen szám, ami teendőt jelent - ezért van
  // a felső sorban, kiemelve, nem a táblázat egy oszlopában elbújva.
  const hatralekOsszesen = dolgozok.reduce((s, d) => s + d.hatralek, 0);
  // A KIFIZETÉS két száma: a bejelentett napi bérek utalással mennek, a
  // fölöttük lévő rész készpénzben. Csak a még ki nem fizetett napokból, mert
  // a kérdés az, hogy MOST mit kell fizetni.
  const nyitottNapok = orak.filter((m) => !m.kifizetve);
  const utalandoOsszesen = nyitottNapok.reduce((s, m) => s + m.utalando, 0);
  const keszpenzOsszesen = nyitottNapok.reduce((s, m) => s + m.keszpenz, 0);

  return (
    <>
      <KrumpelloFejlec
        cim="Munkabér"
        leiras="Ki mikor hány órát dolgozott, és milyen órabéren."
        tol={tol}
        ig={ig}
        utvonal="/krumpello/munkaber"
        jobbOldal={<MunkaoraSzerkeszto dolgozok={dolgozok} />}
      />
      <div className="space-y-8 p-8">
        <div className="flex flex-wrap gap-8 rounded-[var(--radius-lg)] border border-border bg-surface-2 px-6 py-4">
          <Osszesen cimke="Ledolgozott óra" ertek={`${oraOsszesen.toLocaleString("hu-HU")} óra`} />
          <Osszesen cimke="Bér összesen" ertek={formatFt(berOsszesen)} />
          <Osszesen
            cimke="Még jár"
            ertek={formatFt(hatralekOsszesen)}
            hangsuly={hatralekOsszesen > 0 ? "figyelem" : "rendben"}
          />
          <Osszesen cimke="Ebből utalás" ertek={formatFt(utalandoOsszesen)} />
          <Osszesen cimke="Ebből készpénz" ertek={formatFt(keszpenzOsszesen)} />
          <Osszesen cimke="Borravaló" ertek={formatFt(borravaloOsszesen)} />
          <Osszesen
            cimke="Átlagos órabér"
            ertek={oraOsszesen > 0 ? formatFt(Math.round(berOsszesen / oraOsszesen)) : "–"}
          />
        </div>

        <section>
          <h2 className="t-section mb-1">Foglalkoztatási időszakok</h2>
          <p className="mb-3 text-[12.5px] text-text-muted">
            Ki mettől meddig, milyen bejelentéssel dolgozott. A bejelentett napi bér utalással megy, a fölötte
            lévő rész készpénzben – az időszak egyben az elszámolás egysége is.
          </p>
          <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
            <IdoszakKezelo dolgozok={dolgozok} idoszakok={idoszakok} canEdit={canEdit} />
          </div>
        </section>

        <section>
          <h2 className="t-section mb-3">Emberenként</h2>
          {dolgozokOraval.length === 0 ? (
            <p className="text-[13px] text-text-muted">Erre az időszakra nincs rögzített munkaóra.</p>
          ) : (
            <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border bg-surface-2">
              <table className="w-full border-collapse text-[13px]">
                <thead>
                  <tr className="border-b border-border">
                    <th className="px-4 py-2 text-left font-medium text-text-muted">Név</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Óra</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Bér</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Kifizetve</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Még jár</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Borravaló</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Utolsó órabér</th>
                    <th className="px-4 py-2 text-left font-medium text-text-muted">Utoljára dolgozott</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {dolgozokOraval.map((d) => (
                    <tr key={d.id} className="border-b border-border last:border-0">
                      <td className="px-4 py-2.5 text-text-primary">
                        {d.nev}
                        {!d.aktiv && <span className="ml-2 text-[11px] text-text-muted">inaktív</span>}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-text-secondary">
                        {d.ora_osszesen ? `${d.ora_osszesen.toLocaleString("hu-HU")} óra` : "–"}
                      </td>
                      <td className="px-4 py-2.5 text-right font-medium tabular-nums text-text-primary">
                        {d.fizetes_osszesen ? formatFt(d.fizetes_osszesen) : "–"}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-text-success">
                        {d.kifizetve_osszesen ? formatFt(d.kifizetve_osszesen) : "–"}
                      </td>
                      <td
                        className={`px-4 py-2.5 text-right font-medium tabular-nums ${
                          d.hatralek ? "text-text-warning" : "text-text-muted"
                        }`}
                      >
                        {d.hatralek ? formatFt(d.hatralek) : "rendezve"}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-text-secondary">
                        {d.borravalo_osszesen ? formatFt(d.borravalo_osszesen) : "–"}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-text-secondary">
                        {d.alap_orabar != null ? `${formatFt(d.alap_orabar)}/óra` : "–"}
                      </td>
                      <td className="px-4 py-2.5 text-text-secondary">{d.utolso_nap ?? "–"}</td>
                      <td className="px-4 py-2.5 text-right">
                        <IdoszakKifizetes
                          dolgozoId={d.id}
                          nev={d.nev}
                          hatralek={d.hatralek}
                          hatralekosNapok={d.hatralekos_napok}
                          tol={tol}
                          ig={ig}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section>
          <h2 className="t-section mb-3">Naponta</h2>
          {orak.length === 0 ? (
            <p className="text-[13px] text-text-muted">Nincs rögzített nap ebben az időszakban.</p>
          ) : (
            <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-border bg-surface-2">
              <table className="w-full border-collapse text-[13px]">
                <thead>
                  <tr className="border-b border-border">
                    <th className="px-4 py-2 text-left font-medium text-text-muted">Dátum</th>
                    <th className="px-4 py-2 text-left font-medium text-text-muted">Ki</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Óra</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Órabér</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Fizetés</th>
                    <th className="px-4 py-2 text-left font-medium text-text-muted">Bejelentés</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Utalás</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Készpénz</th>
                    <th className="px-4 py-2 text-right font-medium text-text-muted">Borravaló</th>
                    <th className="px-4 py-2 text-left font-medium text-text-muted">Állapot</th>
                    <th className="px-4 py-2 text-left font-medium text-text-muted">Megjegyzés</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {orak.map((m) => (
                    <tr key={m.id} className="border-b border-border last:border-0">
                      <td className="whitespace-nowrap px-4 py-2.5 text-text-primary">{m.datum}</td>
                      <td className="px-4 py-2.5 text-text-primary">{m.dolgozo_nev}</td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-text-secondary">
                        {m.ora != null ? `${m.ora} óra` : "–"}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-text-secondary">
                        {m.orabar != null ? `${formatFt(m.orabar)}/óra` : "–"}
                      </td>
                      <td className="px-4 py-2.5 text-right font-medium tabular-nums text-text-primary">
                        {m.fizetes != null ? formatFt(m.fizetes) : "–"}
                      </td>
                      <td className="px-4 py-2.5 text-text-secondary">
                        {krumpelloBejelentesCimke(m.ervenyes_bejelentes)}
                        {/* Az örökölt és a napra kézzel megadott érték nem
                            ugyanaz: ha valakit egy napra kivettek a
                            bejelentésből, azt látni kell. */}
                        {m.bejelentes_forrasa === "nap" && (
                          <span className="ml-1 text-[11px] text-text-muted">(napra)</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-text-secondary">
                        {m.utalando ? formatFt(m.utalando) : "–"}
                      </td>
                      <td
                        className={`px-4 py-2.5 text-right tabular-nums ${
                          m.keszpenz < 0 ? "text-text-danger" : "text-text-secondary"
                        }`}
                        title={
                          m.keszpenz < 0
                            ? "A bejelentett napi bér többet fizet, mint amennyi aznap járt – az időszak végén kiegyenlítődik."
                            : undefined
                        }
                      >
                        {m.keszpenz ? formatFt(m.keszpenz) : "–"}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-text-secondary">
                        {m.borravalo ? formatFt(m.borravalo) : "–"}
                      </td>
                      <td className="px-4 py-2.5">
                        <KifizetesKapcsolo munkaora={m} />
                      </td>
                      <td className="px-4 py-2.5 text-text-muted">{m.megjegyzes ?? "–"}</td>
                      <td className="px-4 py-2.5 text-right">
                        <MunkaoraSzerkeszto dolgozok={dolgozok} munkaora={m} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

function Osszesen({
  cimke,
  ertek,
  hangsuly,
}: {
  cimke: string;
  ertek: string;
  /** "figyelem" = van még teendő, "rendben" = nincs. */
  hangsuly?: "figyelem" | "rendben";
}) {
  const szin =
    hangsuly === "figyelem" ? "text-text-warning" : hangsuly === "rendben" ? "text-text-success" : "text-text-primary";
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-wide text-text-muted">{cimke}</p>
      <p className={`mt-0.5 text-[17px] font-semibold tabular-nums ${szin}`}>{ertek}</p>
    </div>
  );
}
