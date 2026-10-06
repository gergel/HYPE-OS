"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

export type KiadasNezet = "kifizetett" | "varo";

/** A Kiadások két füle (a felhasználó kérése): a kifizetett kiadások és a
 * KIFIZETÉSRE VÁRÓK (felvezetve, pl. jött róla számla, de még nincs
 * kifizetve). Az URL `kiadas_nezet` paramétere tartja, így a nézet
 * linkelhető és frissítéskor megmarad; a többi paraméter (dátum-szűrő)
 * érintetlen marad. */
export function KiadasNezetFulek({
  nezet,
  kifizetettDb,
  varoDb,
}: {
  nezet: KiadasNezet;
  kifizetettDb: number;
  varoDb: number;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  function href(cel: KiadasNezet) {
    const p = new URLSearchParams(searchParams.toString());
    if (cel === "kifizetett") p.delete("kiadas_nezet");
    else p.set("kiadas_nezet", cel);
    const q = p.toString();
    return q ? `${pathname}?${q}` : pathname;
  }
  const ful = (cel: KiadasNezet, cimke: string, db: number) => (
    <Link
      href={href(cel)}
      scroll={false}
      className={`rounded-[var(--radius)] px-3 py-1.5 text-[13px] ${
        nezet === cel ? "bg-surface-3 font-medium text-text-primary" : "text-text-secondary hover:text-text-primary"
      }`}
    >
      {cimke} <span className="text-text-muted">({db})</span>
    </Link>
  );
  return (
    <div className="mb-4 flex flex-wrap gap-1 border-b border-border pb-2">
      {ful("kifizetett", "Kifizetett", kifizetettDb)}
      {ful("varo", "Kifizetésre vár", varoDb)}
    </div>
  );
}
