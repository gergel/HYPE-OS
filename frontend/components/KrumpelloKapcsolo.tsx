import Link from "next/link";
import { getKrumpelloHozzaferes } from "@/lib/api";

/** Átkapcsolás a Krumpellóra - a HYPE OS fejlécében.
 *
 * Csak annak jelenik meg, aki látja is a Krumpellót: jog nélkül a gomb meg sem
 * rajzolódik, tehát nem is derül ki belőle, hogy létezik ez a rész. A valódi
 * védelmet ettől függetlenül a middleware és a backend adja (lásd
 * routes/krumpello.py) - egy elrejtett gomb sosem védelem, csak azt kerüli el,
 * hogy valaki olyan ajtón kopogtasson, amit úgysem nyitunk ki neki.
 *
 * Szerver-komponens: a jogosultság lekérdezése így a lap renderelésébe épül,
 * nem villan fel és tűnik el a gomb betöltés közben.
 *
 * Nem "kis link a többi ikon között": a Krumpello MÁSIK üzlet pénzügye, az
 * átlépés tudatos döntés - ezért kap saját, narancs keretes gombot a márka
 * nevével. */
export async function KrumpelloKapcsolo() {
  if (!(await getKrumpelloHozzaferes())) return null;

  return (
    <Link
      href="/krumpello"
      title="Átváltás a Krumpello pénzügyre"
      className="flex items-center gap-1.5 rounded-[var(--radius)] border border-[#e8843f]/45 bg-[#e8843f]/10 px-2.5 py-1.5 text-[12.5px] font-semibold text-[#e8843f] transition-colors hover:bg-[#e8843f]/20"
    >
      krumpello
      <span aria-hidden>→</span>
    </Link>
  );
}
