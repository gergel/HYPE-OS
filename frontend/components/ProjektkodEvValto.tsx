import Link from "next/link";

/** Melyik ÉVHEZ tartozik egy projektkód: a kód előtagja mondja meg
 * (HYPE25-… = 2025, HYPE26-… = 2026). Nem a `datum` mező, mert az sokszor
 * üres vagy a szerződés keltezése, a kód viszont mindig az adott év
 * sorozatából jön. */
export const PROJEKTKOD_EVEK = [
  { ev: "2025", elotag: "HYPE25" },
  { ev: "2026", elotag: "HYPE26" },
] as const;

export type ProjektkodEv = (typeof PROJEKTKOD_EVEK)[number]["ev"] | "osszes" | "teendok";

export function evheztartozik(projektkod: string, ev: ProjektkodEv): boolean {
  if (ev === "osszes" || ev === "teendok") return true;
  const elotag = PROJEKTKOD_EVEK.find((e) => e.ev === ev)?.elotag;
  return !!elotag && projektkod.trim().toUpperCase().startsWith(elotag);
}

/** Évenkénti nézetváltó a projektkódok fölött.
 *
 * Linkekből áll (nem kliens-oldali state), így a nézet a címben is benne van:
 * meg lehet osztani, könyvjelzőzni, és a lista fejlécében látszó darabszám is
 * a valóban mutatott sorokat számolja. Az "Összes" azért kell, mert a régebbi
 * (HYPE24-es) és a más kódrendszerű munkák egyik évhez sem tartoznak - azok
 * nélküle láthatatlanná válnának. */
export function ProjektkodEvValto({
  aktiv,
  darabszamok,
}: {
  aktiv: ProjektkodEv;
  darabszamok: Record<ProjektkodEv, number>;
}) {
  const nezetek: { ev: ProjektkodEv; cimke: string }[] = [
    ...PROJEKTKOD_EVEK.map((e) => ({ ev: e.ev as ProjektkodEv, cimke: e.ev })),
    { ev: "osszes", cimke: "Összes" },
    // A negyedik nézet nem évre szűr, hanem TEENDŐRE bont: hol nincs még
    // szerződés, hol hiányzik már csak a TIG, és mit nem fizettek ki. A
    // többi nézetben ezek elvegyülnek a kész munkák közt.
    { ev: "teendok", cimke: "Teendők" },
  ];

  return (
    <div className="mb-4 flex gap-2">
      {nezetek.map(({ ev, cimke }) => (
        <Link
          key={ev}
          href={`/projektek/project-kodok?ev=${ev}`}
          className={`rounded-[var(--radius)] px-3 py-1.5 text-[13px] ${
            aktiv === ev ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:bg-surface-3"
          }`}
        >
          {cimke}
          <span className="ml-1.5 text-text-muted">{darabszamok[ev]}</span>
        </Link>
      ))}
    </div>
  );
}
