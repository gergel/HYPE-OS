import Link from "next/link";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { UtokovetesLista, UtokovetesTabla, fazisa } from "@/components/UtokovetesTabla";
import { getUtokovetesOverview } from "@/lib/api";

const NEZETEK = [
  { kulcs: "", cimke: "Áttekintés" },
  { kulcs: "admin", cimke: "Admin lista" },
] as const;

/** Utókövetés - EGY oldalon mutatja minden diszpózott projekthez tartozó
 * eseti szerződés + teljesítési igazolás + kifizetés + forgatás utáni
 * kérdőívválasz állapotát, hogy ne kelljen projektenként külön-külön több
 * oldalt végignézni. A tényleges kezelés (mentés/generálás/küldés/kihagyás)
 * a projekt utókövetés-oldalán történik - ez csak az áttekintés.
 *
 * Két nézet van, és a nézet a címben is benne van (?nezet=admin), hogy
 * linkelhető és megosztható legyen:
 *  - ÁTTEKINTÉS (alap): a projektek fázisonként, egymás melletti oszlopokban -
 *    mi kész, hol kell már csak utalni, hol hiányzik a TIG, hol a szerződés.
 *  - ADMIN LISTA: a részletes, szűrhető-rendezhető táblázat minden fázissal. */
export default async function UtokovetesPage({
  searchParams,
}: {
  searchParams: Promise<{ nezet?: string }>;
}) {
  const { nezet } = await searchParams;
  const admin = nezet === "admin";
  const rows = await getUtokovetesOverview();
  const keszDarab = rows.filter((r) => fazisa(r) === "kesz").length;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card
          title={
            admin
              ? `Utókövetés (${rows.length} diszpózott projekt)`
              : `Utókövetés – ${keszDarab} kész, ${rows.length - keszDarab} folyamatban`
          }
          actions={
            <div className="flex items-center gap-1 rounded-[var(--radius)] border border-border p-0.5">
              {NEZETEK.map((n) => {
                const aktiv = (n.kulcs === "admin") === admin;
                return (
                  <Link
                    key={n.kulcs}
                    href={n.kulcs ? `/utokovetes?nezet=${n.kulcs}` : "/utokovetes"}
                    className={`rounded-[var(--radius)] px-2.5 py-1 text-[12.5px] transition-colors ${
                      aktiv ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:text-text-primary"
                    }`}
                  >
                    {n.cimke}
                  </Link>
                );
              })}
            </div>
          }
        >
          {admin ? <UtokovetesLista rows={rows} /> : <UtokovetesTabla rows={rows} />}
        </Card>
      </div>
    </div>
  );
}
