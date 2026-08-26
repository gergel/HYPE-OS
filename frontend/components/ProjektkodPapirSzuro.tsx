import Link from "next/link";
import type { ProjectCode } from "@/lib/api";

/** KIHAGYOTT és KIKÜLDVE-DE-VISSZA-NEM-JÖTT papírok szűrője a projektkódok
 * fölött.
 *
 * Van, amikor tudatosan nem készül papír: keret alatt az eseti szerződés marad
 * el, egy hosszú együttműködésnél inkább a TIG. Ilyenkor a papír állapota
 * "Kihagyva", a projektkód pedig LEZÁRTNAK számít - vagyis a teendők közül is
 * kiesik, és a listán is a kész munkák közé vegyül.
 *
 * Van, amikor viszont VAN papír, csak épp KIKÜLDVE áll, aláírva még nem jött
 * vissza - ez is LEZÁRTNAK számít (nincs rajtunk teendő, lásd
 * models/megrendeloi_papir.py LEZART_ALLAPOTOK), de a megrendelő felől még
 * lóg egy alá nem írt papír, amit időnként érdemes rákérdezni.
 *
 * Mindkét eset rendben van a napi munkához, de évzáráskor, könyvelői
 * egyeztetésnél vagy egy utólagos átnézésnél pont ezek a munkák a kérdés:
 * "melyikről nincs papírunk, és tényleg nem is kellett?", illetve "melyik van
 * még kint aláírásra?" Ezek nélkül a szűrők nélkül ezt csak egyesével, az
 * adatlapokat megnyitva lehetne végigjárni.
 *
 * A SZERZŐDÉS és a TIG külön szűrő, mert külön is szokás kihagyni/kiküldeni
 * őket - a kettő nem ugyanaz a helyzet, és nem is ugyanaz a teendő.
 *
 * Ami NEM kerül bele: ahol számla sincs (kihagytuk, papír nélkül van
 * elszámolva, vagy elmaradt). Ott a hiányzó szerződés és TIG nem elmaradás,
 * hanem következmény - nincs is mihez elkészíteni őket -, és az okuk amúgy is
 * ott áll a projektkódon, indoklással. Ha ezek is felkerülnének a listára, a
 * szűrő pont a lényegét veszítené el: a néhány valódi hiányt elfedné a sok
 * megmagyarázott eset. */
export const PAPIR_SZUROK = [
  { kulcs: "szerzodes-kihagyva", cimke: "Szerződés kihagyva" },
  { kulcs: "szerzodes-kikuldve", cimke: "Szerződés kiküldve, várjuk vissza" },
  { kulcs: "tig-kihagyva", cimke: "TIG kihagyva" },
  { kulcs: "tig-kikuldve", cimke: "TIG kiküldve, várjuk vissza" },
] as const;

export type PapirSzuro = (typeof PAPIR_SZUROK)[number]["kulcs"] | "mind";

export function papirSzurore(pc: ProjectCode, szuro: PapirSzuro): boolean {
  if (szuro === "mind") return true;
  // AHOL NINCS SZÁMLA, ott a kihagyott/kiküldött papír nem hiányosság, hanem
  // következmény: nincs is mihez szerződést és TIG-et készíteni. Ez a szűrő
  // azt keresi, ahol PAPÍRT hagytunk ki (vagy küldtünk ki, és várunk rá) egy
  // egyébként rendes, kiszámlázott munkán - ha a számlát is kihagytuk (vagy
  // az egész munka papír nélkül van elszámolva, vagy elmaradt), akkor a
  // papír hiánya maga a döntés, amit már megindokoltunk. Lásd backend
  // services/megrendeloi_szamla.szamlat_varunk.
  if (pc.szamla_kell === false) return false;
  if (szuro === "szerzodes-kihagyva") return pc.szerzodes_kihagyva === true;
  if (szuro === "szerzodes-kikuldve") return pc.szerzodes_kikuldve_varjuk === true;
  if (szuro === "tig-kihagyva") return pc.tig_kihagyva === true;
  return pc.tig_kikuldve_varjuk === true;
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
