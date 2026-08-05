import Link from "next/link";
import { formatDate, type JsonRecord } from "@/lib/api";
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

/** A munkatárshoz tartozó egyéb (nem a havi bérezésből jövő) kiadások:
 * melyik projektkódhoz, mekkora összeg, és mikor vonódott le. Szándékosan nem
 * a generikus kapcsolt-tábla, mert itt pont ez a három dolog a kérdés. */
export function EgyebKiadasok({
  kiadasok,
  projektkodNevek,
}: {
  kiadasok: JsonRecord[];
  projektkodNevek: Record<number, string>;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="os-table w-full border-collapse text-[13px]">
        <thead>
          <tr>
            <th className="text-left">Megnevezés</th>
            <th className="text-left">Projektkód</th>
            <th className="text-left">Levonás dátuma</th>
            <th className="text-right">Összeg</th>
          </tr>
        </thead>
        <tbody>
          {kiadasok.map((k) => {
            const kodId = typeof k.project_code_id === "number" ? k.project_code_id : null;
            const osszeg = szam(k.brutto) ?? szam(k.netto);
            return (
              <tr key={k.id}>
                <td>
                  <Link href={`/penzugyek/kiadas/${k.id}`} className="text-text-accent hover:underline">
                    {typeof k.megnevezes === "string" && k.megnevezes ? k.megnevezes : `Kiadás #${k.id}`}
                  </Link>
                </td>
                <td>
                  {kodId && projektkodNevek[kodId] ? (
                    <Link
                      href={`/projektek/project-kodok/${kodId}`}
                      className="text-text-accent hover:underline"
                    >
                      {projektkodNevek[kodId]}
                    </Link>
                  ) : (
                    <span className="text-text-muted">Nincs projektkódhoz kötve</span>
                  )}
                </td>
                <td className="text-text-secondary">{formatDate(levonasDatuma(k))}</td>
                <td className="text-right tabular-nums">{osszeg === null ? "–" : formatHuf(osszeg)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
