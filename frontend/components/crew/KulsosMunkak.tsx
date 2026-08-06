import Link from "next/link";
import { formatFt } from "@/lib/ido";
import type { KulsosMunkakOsszesites } from "@/lib/api";

/** Egy külsős munkatárs munkái: miken vett részt, mennyiért, és hol a papír.
 *
 * A külsősöknél nincs havi bérelszámolás (az a belsősök világa): egy külsős
 * PROJEKTENKÉNT dolgozik - vagy eseti szerződéssel, vagy álló
 * keretszerződéssel -, és a végén a TIG mondja meg, mennyiért csinálta. Ez a
 * blokk pont ezt gyűjti egy helyre: a projektet, az összeget, és minden hozzá
 * tartozó dokumentumot (szerződés, TIG, számla).
 *
 * Ha van álló keretszerződése, projektenként NINCS külön szerződés - azt
 * egyszer, a lista fölött mutatjuk, és a soroknál csak jelezzük.
 *
 * A tábla szándékosan kevés oszlopos: a kártya egy féloldalas hasábban áll, és
 * hét oszlop mellett a forintok kicsúsztak volna a képből. Ezért a projekt
 * cellája viszi a kódot, a megbízás tárgyát és a dokumentumokat is, az összeg
 * pedig egy oszlopban a nettót és alatta a bruttót. */
export function KulsosMunkak({ adat }: { adat: KulsosMunkakOsszesites }) {
  const { projektek } = adat;

  if (projektek.length === 0) {
    return (
      <p className="text-[13px] text-text-muted">
        Ez a munkatárs még egyetlen projekten sem vett részt szerződéssel vagy TIG-gel.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {adat.keretszerzodes_id !== null && (
        <p className="text-[13px] text-text-secondary">
          Álló keretszerződéssel dolgozik –{" "}
          <Link href={`/szerzodesek/${adat.keretszerzodes_id}`} className="text-text-accent hover:underline">
            keretszerződés megnyitása
          </Link>
          {adat.keretszerzodes_url && (
            <>
              {" ("}
              <a
                href={adat.keretszerzodes_url}
                target="_blank"
                rel="noreferrer"
                className="text-text-accent hover:underline"
              >
                aláírt PDF
              </a>
              {")"}
            </>
          )}
          , ezért a projekteknél nincs külön szerződés.
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="os-table w-full border-collapse text-[13px]">
          <thead>
            <tr>
              <th className="text-left">Projekt</th>
              <th className="text-left">Forgatás</th>
              <th className="text-left">TIG</th>
              <th className="text-right">Összeg</th>
            </tr>
          </thead>
          <tbody>
            {projektek.map((p, i) => (
              <tr key={`${p.project_id ?? "nincs"}-${i}`} className="align-top">
                <td>
                  <span className="flex flex-wrap items-baseline gap-x-2">
                    {p.project_id ? (
                      <Link href={`/projektek/${p.project_id}`} className="text-text-accent hover:underline">
                        {p.project_nev ?? `#${p.project_id}`}
                      </Link>
                    ) : (
                      (p.project_nev ?? "–")
                    )}
                    {p.projektkod && <span className="text-[12px] text-text-muted">{p.projektkod}</span>}
                  </span>
                  {p.megbizas_targya && (
                    <span className="mt-0.5 block text-[12px] text-text-secondary">{p.megbizas_targya}</span>
                  )}
                  <span className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[12px]">
                    {p.dokumentumok.map((d) => (
                      <a
                        key={d.url + d.cimke}
                        href={d.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-text-accent hover:underline"
                      >
                        {d.cimke}
                      </a>
                    ))}
                    {p.keretszerzodessel && <span className="text-text-muted">szerződés: keretszerződés</span>}
                    {p.dokumentumok.length === 0 && !p.keretszerzodessel && (
                      <span className="text-text-muted">nincs dokumentum</span>
                    )}
                  </span>
                </td>
                <td className="whitespace-nowrap text-text-secondary">{p.forgatas_datuma ?? "–"}</td>
                <td className="text-text-secondary">
                  {p.tig_allapot ?? "Nincs még TIG"}
                  {p.szamla_kifizetve && <span className="mt-0.5 block text-text-success">számla kifizetve</span>}
                </td>
                <td className="whitespace-nowrap text-right tabular-nums">
                  {p.netto === null ? "–" : formatFt(p.netto)}
                  {p.brutto !== null && p.brutto !== p.netto && (
                    <span className="mt-0.5 block text-[12px] text-text-muted">{formatFt(p.brutto)} bruttó</span>
                  )}
                </td>
              </tr>
            ))}
            <tr className="font-medium">
              <td colSpan={3} className="text-text-secondary">
                Összesen ({projektek.length} projekt)
              </td>
              <td className="whitespace-nowrap text-right tabular-nums text-text-primary">
                {formatFt(adat.osszes_netto)}
                <span className="mt-0.5 block text-[12px] font-normal text-text-muted">
                  {formatFt(adat.osszes_brutto)} bruttó
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
