import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { UtokovetesLista } from "@/components/UtokovetesLista";
import { UtokovetesNezetek } from "@/components/UtokovetesNezetek";
import { fazisa } from "@/lib/utokovetes";
import { getUtokovetesOverview } from "@/lib/api";

/** Utókövetés - EGY oldalon mutatja minden diszpózott projekthez tartozó
 * eseti szerződés + teljesítési igazolás + kifizetés + forgatás utáni
 * kérdőívválasz állapotát, hogy ne kelljen projektenként külön-külön több
 * oldalt végignézni. A tényleges kezelés (mentés/generálás/küldés/kihagyás)
 * a projekt utókövetés-oldalán történik - ez csak az áttekintés.
 *
 * Két nézet van, EGY adatlekérésből (a váltás nem tölt újra - lásd
 * UtokovetesNezetek):
 *  - ÁTTEKINTÉS (alap): a projektek fázisonként, egymás melletti oszlopokban -
 *    mi kész, hol kell már csak utalni, hol hiányzik a TIG, hol a szerződés.
 *    Kereshető, rendezhető, és a kész projektek elrejthetők.
 *  - ADMIN LISTA: a részletes, szűrhető-rendezhető táblázat minden fázissal.
 *
 * A kezdő nézetet a cím adja (?nezet=admin), hogy a link megosztható legyen. */
export default async function UtokovetesPage({
  searchParams,
}: {
  searchParams: Promise<{ nezet?: string }>;
}) {
  const { nezet } = await searchParams;
  const rows = await getUtokovetesOverview();
  const keszDarab = rows.filter((r) => fazisa(r) === "kesz").length;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <Card
          title={`Utókövetés – ${rows.length} projekt, ${keszDarab} kész, ${rows.length - keszDarab} folyamatban`}
        >
          <UtokovetesNezetek
            rows={rows}
            kezdeti={nezet === "admin" ? "admin" : "attekintes"}
            lista={<UtokovetesLista rows={rows} />}
          />
        </Card>
      </div>
    </div>
  );
}
