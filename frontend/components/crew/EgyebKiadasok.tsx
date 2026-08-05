import Link from "next/link";
import { formatDate, type EvesKoltseg, type JsonRecord } from "@/lib/api";
import { honapCimke } from "@/lib/ido";
import { formatHuf } from "@/lib/penz";

/** A levonás napja. A kiadásokon több dátum is lehet (fizetés dátuma,
 * kiadás dátuma, fizetési határidő) - a tényleges levonást a fizetés napja
 * jelenti; ha az még nincs meg, a kiadás napja, végül a határidő a
 * legjobb elérhető közelítés. */
function levonasDatuma(kiadas: JsonRecord): string | null {
  for (const kulcs of ["fizetes_datuma", "kiadas_datuma", "fizetes_hatarideje"]) {
    const ertek = kiadas[kulcs];
    if (typeof ertek === "string" && ertek) return ertek;
  }
  return null;
}

function szam(ertek: unknown): number | null {
  return typeof ertek === "number" ? ertek : null;
}

/** Egy sor az összesített listában. Két forrásból jöhet: a pénzügyi kiadás
 * (számla), és a havi elszámoláshoz felvitt tétel (túlóra, benzin, levonás) -
 * a `elojeles` mező tartalmazza, hogy hozzáadódik vagy levonódik. */
type Sor = {
  kulcs: string;
  megnevezes: string;
  href: string | null;
  projektkodId: number | null;
  projektkod: string | null;
  /** Amit a "Levonás dátuma" oszlopban mutatunk. */
  datum: string | null;
  /** Dátum híján ez azonosítja a sort (a havi tételeknél az elszámolás hónapja). */
  datumPotlek: string | null;
  osszeg: number | null;
  /** A havi tételeknél az elszámolás hónapja - ebből derül ki, melyik
   * hónaphoz vittük fel. */
  honapCimke: string | null;
  levonas: boolean;
};

/** Rendezés: a legfrissebb elöl. Dátum nélküli sorok a végére. */
function rendez(sorok: Sor[]): Sor[] {
  return [...sorok].sort((a, b) => {
    const ad = a.datum ?? a.datumPotlek ?? "";
    const bd = b.datum ?? b.datumPotlek ?? "";
    if (ad === bd) return 0;
    if (!ad) return 1;
    if (!bd) return -1;
    return ad < bd ? 1 : -1;
  });
}

function kiadasSor(k: JsonRecord): Sor {
  const kodId = typeof k.project_code_id === "number" ? k.project_code_id : null;
  return {
    kulcs: `kiadas-${k.id}`,
    megnevezes: typeof k.megnevezes === "string" && k.megnevezes ? k.megnevezes : `Kiadás #${k.id}`,
    href: `/penzugyek/kiadas/${k.id}`,
    projektkodId: kodId,
    projektkod: null,
    datum: levonasDatuma(k),
    datumPotlek: null,
    osszeg: szam(k.brutto) ?? szam(k.netto),
    honapCimke: null,
    levonas: false,
  };
}

/** A havi elszámoláshoz felvitt extrák és levonások - az ALAPBÉR nélkül: ez a
 * blokk azt mutatja, mi jött a fix részen FELÜL. */
function haviSorok(evek: EvesKoltseg[]): Sor[] {
  const sorok: Sor[] = [];
  for (const ev of evek) {
    for (const honap of ev.honapok) {
      for (const tetel of honap.tetelek) {
        if (tetel.tipus === "alapber") continue;
        sorok.push({
          kulcs: `tetel-${tetel.id}`,
          megnevezes: tetel.megnevezes,
          href: `/belsos-tig/${tetel.employee_id}/${honap.ev}/${honap.honap}`,
          projektkodId: tetel.project_code_id,
          projektkod: tetel.projektkod,
          datum: tetel.datum,
          // Pontos dátum nélkül az elszámolás hónapjának elseje rendez - a
          // hónapon belüli sorrend ilyenkor úgysem ismert.
          datumPotlek: `${honap.ev}-${String(honap.honap).padStart(2, "0")}-01`,
          osszeg: tetel.osszeg,
          honapCimke: honapCimke(honap.ev, honap.honap),
          levonas: tetel.tipus === "levonando",
        });
      }
    }
  }
  return sorok;
}

/** A munkatárs MINDEN extrája egy helyen: a pénzügyi kiadások (számlák) és a
 * havi elszámoláshoz felvitt tételek (túlóra, benzin, étkezés, levonások)
 * együtt, egyetlen végösszeggel.
 *
 * Azért egy táblában, mert a kérdés ("mi jött az alapbéren felül, és mennyi
 * ez összesen?") nem tesz különbséget aszerint, hogy az összeg számlaként
 * érkezett-e vagy a havi elszámoláshoz vittük fel. A levonandó tételek
 * MÍNUSSZAL számítanak bele (lásd backend elojeles_osszeg). */
export function EgyebKiadasok({
  kiadasok,
  koltsegek,
  projektkodNevek,
}: {
  kiadasok: JsonRecord[];
  /** A havi bontás - ebből jönnek az extrák és a levonások. */
  koltsegek: EvesKoltseg[];
  projektkodNevek: Record<number, string>;
}) {
  const tetelSorok = haviSorok(koltsegek);
  // Ugyanaz a költség kiadás-sorként ÉS havi tételként is létezhet (a Notion
  // "Belsős extra kiadások" táblája mindkettőként bejön) - ilyenkor a havi
  // tétel a részletesebb, a kiadás-sort kihagyjuk, hogy ne számítson duplán.
  const tetelbenSzereplo = new Set(
    koltsegek.flatMap((ev) =>
      ev.honapok.flatMap((h) => h.tetelek.map((t) => t.expense_id).filter((id): id is number => id !== null)),
    ),
  );
  const kiadasSorok = kiadasok
    .filter((k) => !(typeof k.id === "number" && tetelbenSzereplo.has(k.id)))
    .map(kiadasSor);
  const sorok = rendez([...kiadasSorok, ...tetelSorok]);


  const kiadasOsszeg = kiadasSorok.reduce((sum, s) => sum + (s.osszeg ?? 0), 0);
  const extraOsszeg = tetelSorok.filter((s) => !s.levonas).reduce((sum, s) => sum + (s.osszeg ?? 0), 0);
  const levonasOsszeg = tetelSorok.filter((s) => s.levonas).reduce((sum, s) => sum + (s.osszeg ?? 0), 0);
  const mindosszesen = kiadasOsszeg + extraOsszeg - levonasOsszeg;

  if (sorok.length === 0) {
    return <p className="text-[13px] text-text-muted">Nincs egyéb kiadás vagy havi extra ehhez a munkatárshoz.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="os-table w-full border-collapse text-[13px]">
          <thead>
            <tr>
              <th className="text-left">Megnevezés</th>
              <th className="text-left">Elszámolás</th>
              <th className="text-left">Projektkód</th>
              <th className="text-left">Levonás dátuma</th>
              <th className="text-right">Összeg</th>
            </tr>
          </thead>
          <tbody>
            {sorok.map((s) => {
              const kod = s.projektkod ?? (s.projektkodId ? projektkodNevek[s.projektkodId] : null);
              return (
                <tr key={s.kulcs}>
                  <td>
                    {s.href ? (
                      <Link href={s.href} className="text-text-accent hover:underline">
                        {s.megnevezes}
                      </Link>
                    ) : (
                      s.megnevezes
                    )}
                  </td>
                  <td className="text-text-secondary">{s.honapCimke ?? "Számla"}</td>
                  <td>
                    {s.projektkodId && kod ? (
                      <Link
                        href={`/projektek/project-kodok/${s.projektkodId}`}
                        className="text-text-accent hover:underline"
                      >
                        {kod}
                      </Link>
                    ) : (
                      <span className="text-text-muted">Nincs projektkódhoz kötve</span>
                    )}
                  </td>
                  <td className="text-text-secondary">{formatDate(s.datum)}</td>
                  <td
                    className={`text-right tabular-nums ${s.levonas ? "text-text-danger" : ""}`}
                  >
                    {s.osszeg === null ? "–" : s.levonas ? `− ${formatHuf(s.osszeg)}` : formatHuf(s.osszeg)}
                  </td>
                </tr>
              );
            })}
            <tr className="font-medium">
              <td colSpan={4} className="text-text-secondary">
                Mindösszesen
              </td>
              <td className="text-right text-text-primary tabular-nums">{formatHuf(mindosszesen)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* A végösszeg összetevői: melyik forrásból mennyi jött. */}
      <p className="text-[12px] text-text-muted">
        Havi extrák: <span className="text-text-secondary">{formatHuf(extraOsszeg)}</span>
        {levonasOsszeg > 0 && (
          <>
            {" · "}Levonások: <span className="text-text-danger">− {formatHuf(levonasOsszeg)}</span>
          </>
        )}
        {" · "}Egyéb kiadások (számlák): <span className="text-text-secondary">{formatHuf(kiadasOsszeg)}</span>
      </p>
    </div>
  );
}
