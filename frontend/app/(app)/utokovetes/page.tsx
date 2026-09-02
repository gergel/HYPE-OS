import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { UtokovetesLista } from "@/components/UtokovetesLista";
import { UtokovetesNezetek } from "@/components/UtokovetesNezetek";
import { UtokovetesProjektKereso } from "@/components/UtokovetesProjektKereso";
import { fazisa } from "@/lib/utokovetes";
import {
  getProjects,
  getUtokovetesOverview,
  getUtokovetesOverviewProjectCodes,
  type UtokovetesOverview,
} from "@/lib/api";

/** Utókövetés - EGY oldalon mutatja minden diszpózott projekthez tartozó
 * eseti szerződés + teljesítési igazolás + kifizetés + forgatás utáni
 * kérdőívválasz állapotát, hogy ne kelljen projektenként külön-külön több
 * oldalt végignézni. A tényleges kezelés (mentés/generálás/küldés/kihagyás)
 * a projekt utókövetés-oldalán történik - ez csak az áttekintés.
 *
 * A forgatás NÉLKÜLI, közvetlenül projektkódhoz kötött papírozás (backend
 * utokovetes_admin.py "projektkód-szintű ág") NEM külön szakasz, hanem
 * ugyanennek az egy listának a sorai (a felhasználó kérése: "csak egy nagy
 * utókövetés rész legyen"). Ezek a sorok negatív azonosítóval utaznak
 * (-project_code_id), és a projektkód-részletnézet nyílik rájuk - lásd
 * UtokovetesDetailModal.
 *
 * Két nézet van, EGY adatlekérésből (a váltás nem tölt újra - lásd
 * UtokovetesNezetek):
 *  - ÁTTEKINTÉS (alap): a tételek fázisonként, egymás melletti oszlopokban -
 *    mi kész, hol kell már csak utalni, hol hiányzik a TIG, hol a szerződés.
 *    Kereshető, rendezhető, és a kész tételek elrejthetők.
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
  const [projektSorok, projektek, projektkodSorok] = await Promise.all([
    getUtokovetesOverview(),
    getProjects(20000),
    getUtokovetesOverviewProjectCodes(),
  ]);

  // A projektkód-szintű sorok UGYANOLYAN alakra hozva, mint a projektesek -
  // a mezőnevek szándékosan azonosak a két backend-válaszban, csak az
  // azonosító és a dátum tér el. A negatív project_id jelzi végig a
  // rendszernek (kártya-kattintás, modál, admin lista sor-link), hogy ez
  // projektkód, nem projekt.
  const kodSorok: UtokovetesOverview[] = projektkodSorok.map((pk) => ({
    project_id: -pk.project_code_id,
    project_nev: pk.project_nev ?? pk.projektkod,
    projektkod: pk.projektkod,
    forgatas_datuma: null,
    forgatas_datuma_vege: null,
    szerzodes_osszes: pk.szerzodes_osszes,
    szerzodes_fuggo: pk.szerzodes_fuggo,
    tig_ready: pk.tig_ready,
    tig_osszes: pk.tig_osszes,
    tig_fuggo: pk.tig_fuggo,
    alairas_varo: pk.alairas_varo,
    kifizetes_osszes: pk.kifizetes_osszes,
    kifizetes_fuggo: pk.kifizetes_fuggo,
    kesz: pk.kesz,
    visszajelzes_darab: 0,
  }));
  const rows = [...projektSorok, ...kodSorok];
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
          title={`Utókövetés – ${rows.length} tétel, ${keszDarab} kész, ${rows.length - keszDarab} folyamatban`}
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
      </div>
    </div>
  );
}
