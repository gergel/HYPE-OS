import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { UtokovetesLista } from "@/components/UtokovetesLista";
import { UtokovetesNezetek } from "@/components/UtokovetesNezetek";
import { UtokovetesProjektKereso } from "@/components/UtokovetesProjektKereso";
import { fazisa } from "@/lib/utokovetes";
import { getProjects, getUtokovetesOverview } from "@/lib/api";

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
  // A limit szándékosan bő: a projektek száma több ezer, és a keresőnek a
  // TELJES állományt kell látnia - pont az a dolga, hogy az áttekintő
  // hatóköréből kimaradó projektet is meg lehessen nyitni.
  const [rows, projektek] = await Promise.all([getUtokovetesOverview(), getProjects(20000)]);
  const keszDarab = rows.filter((r) => fazisa(r) === "kesz").length;
  // Csak a kereséshez kellő pár mező megy le a kliensre, nem a teljes
  // projekt-rekord (annak Notion-mezőstül több MB lenne).
  const keresoProjektek = projektek.map((p) => ({
    id: p.id,
    nev: p.nev ?? null,
    projektkod: p.projektkod_szoveg ?? null,
    datum: p.forgatas_datuma,
  }));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <Card
          title={`Utókövetés – ${rows.length} projekt, ${keszDarab} kész, ${rows.length - keszDarab} folyamatban`}
        >
          <div className="mb-4">
            <UtokovetesProjektKereso
              projektek={keresoProjektek}
              listazott={rows.map((r) => r.project_id)}
            />
          </div>
          <UtokovetesNezetek
            rows={rows}
            kezdeti={nezet === "admin" ? "admin" : "attekintes"}
            lista={<UtokovetesLista rows={rows} />}
          />
        </Card>

        {/* A korábbi "Alvállalkozói papírozás forgatás nélkül" külön tábla
            SZÁNDÉKOSAN nincs többé itt (a felhasználó kérése): a papírozást
            összevontuk, ezek a tételek a fenti áttekintésben és a projektkód
            oldalain jelennek meg - a külön szakasz csak duplázta őket. */}
      </div>
    </div>
  );
}
