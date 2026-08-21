import Link from "next/link";
import type { ProjectCode } from "@/lib/api";

/** KIHAGYOTT PAPÍROK szűrője a projektkódok fölött.
 *
 * Van, amikor tudatosan nem készül papír: keret alatt az eseti szerződés marad
 * el, egy hosszú együttműködésnél inkább a TIG. Ilyenkor a papír állapota
 * "Kihagyva", a projektkód pedig LEZÁRTNAK számít - vagyis a teendők közül is
 * kiesik, és a listán is a kész munkák közé vegyül.
 *
 * Ez rendben van a napi munkához, de évzáráskor, könyvelői egyeztetésnél vagy
 * egy utólagos átnézésnél pont ez a néhány munka a kérdés: "melyikről nincs
 * papírunk, és tényleg nem is kellett?" Ezek nélkül a szűrők nélkül ezt csak
 * egyesével, az adatlapokat megnyitva lehetne végigjárni.
 *
 * A SZERZŐDÉS és a TIG külön szűrő, mert külön is szokás kihagyni őket - a
 * kettő nem ugyanaz a helyzet, és nem is ugyanaz a teendő. */
export const PAPIR_SZUROK = [
  { kulcs: "szerzodes-kihagyva", cimke: "Szerződés kihagyva" },
  { kulcs: "tig-kihagyva", cimke: "TIG kihagyva" },
] as const;

export type PapirSzuro = (typeof PAPIR_SZUROK)[number]["kulcs"] | "mind";

export function papirSzurore(pc: ProjectCode, szuro: PapirSzuro): boolean {
  if (szuro === "szerzodes-kihagyva") return pc.szerzodes_kihagyva === true;
  if (szuro === "tig-kihagyva") return pc.tig_kihagyva === true;
  return true;
}

/** Érvényes-e a címben kapott érték - ismeretlen esetén a szűretlen lista jön,
 * nem egy üres oldal. */
export function papirSzuroErteke(ertek: string | undefined): PapirSzuro {
  return PAPIR_SZUROK.some((s) => s.kulcs === ertek) ? (ertek as PapirSzuro) : "mind";
}

/** Linkekből áll, mint az évváltó: a nézet a címben van, tehát megosztható és
 * könyvjelzőzhető. Az ÉV megmarad - a két szűrő egymást szűkíti, nem váltja ki
 * egymást (aki 2026-ot néz, arra az évre kíváncsi). */
export function ProjektkodPapirSzuro({
  ev,
  aktiv,
  darabszamok,
}: {
  ev: string;
  aktiv: PapirSzuro;
  darabszamok: Record<PapirSzuro, number>;
}) {
  const nezetek: { kulcs: PapirSzuro; cimke: string }[] = [
    { kulcs: "mind", cimke: "Mind" },
    ...PAPIR_SZUROK.map((s) => ({ kulcs: s.kulcs as PapirSzuro, cimke: s.cimke })),
  ];

  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <span className="text-[12.5px] text-text-muted">Papírozás:</span>
      {nezetek.map(({ kulcs, cimke }) => (
        <Link
          key={kulcs}
          href={`/projektek/project-kodok?ev=${ev}${kulcs === "mind" ? "" : `&papir=${kulcs}`}`}
          className={`rounded-[var(--radius)] border px-3 py-1 text-[12.5px] ${
            aktiv === kulcs
              ? "border-border-strong bg-surface-3 text-text-primary"
              : "border-border text-text-secondary hover:bg-surface-3"
          }`}
        >
          {cimke}
          <span className="ml-1.5 text-text-muted">{darabszamok[kulcs]}</span>
        </Link>
      ))}
    </div>
  );
}
