import { TopBar } from "@/components/TopBar";
import { UtomunkaContent } from "@/components/deliverable/UtomunkaContent";
import {
  getAllapotBeallitasok,
  getCurrentUser,
  getDeliverables,
  getEmployees,
  getFieldTypes,
  getKartyaMezok,
  getMyPagePermissions,
  getProjects,
  getVinyoOptionsReszletes,
} from "@/lib/api";
import { canDoPageAction, szerepkorei } from "@/lib/permissions";

// Csak ennyi legutóbb módosított/létrehozott rekordot töltünk be azonnal (a
// backend list_items alapértelmezetten updated_at szerint csökkenő sorrendben
// ad vissza, lásd api/crud_router.py) - a régebbi, rég nem használt anyagok/
// forgatások a háttérben töltődnek be (lásd UtomunkaContent), hogy sok
// felhalmozott történeti rekord esetén se legyen lassú az oldal első betöltése.
const INITIAL_BATCH = 200;
const PAGE = "/utomunka";

/** Az Utómunka oldal két nézetet ad: egy "Vágó nézetet" (állapot szerinti
 * tábla + forgatások naptár + vinyó szerinti tábla - hogy a vágóknak ne a
 * nyers adattáblát kelljen böngészniük), és a régi "Admin listát" (a teljes
 * DataTable, szűréssel/rendezéssel/törléssel). */
export default async function UtomunkaPage({
  searchParams,
}: {
  searchParams: Promise<{ szures?: string }>;
}) {
  // ?szures=lejart: a dashboard "lejárt utómunka határidő" figyelmeztetése
  // ezzel nyitja az oldalt - csak a lejárt anyagok látszanak (a szűrés a
  // felületen kikapcsolható, lásd UtomunkaContent).
  const { szures } = await searchParams;
  const [
    deliverables,
    employees,
    projects,
    fieldTypes,
    vinyoReszletes,
    allapotBeallitasok,
    kartyaMezok,
    pagePermissions,
    currentUser,
  ] = await Promise.all([
    getDeliverables(INITIAL_BATCH),
    getEmployees(),
    getProjects(INITIAL_BATCH),
    getFieldTypes("deliverable"),
    // A lista mellett azt is megmondja, kezelheti-e a lekérő a vinyó-neveket
    // (a felhasználó kérése: külön, adminból adható jogosultság).
    getVinyoOptionsReszletes(),
    getAllapotBeallitasok(),
    getKartyaMezok(),
    getMyPagePermissions(),
    getCurrentUser(),
  ]);

  const statusOptions = fieldTypes.allapot?.options ?? [];
  const calendarProjects = projects.map((p) => ({
    id: p.id,
    nev: p.nev,
    forgatas_datuma: p.forgatas_datuma,
    // A TÉNYLEGES záró nap (kézi + naptár/Notion tükör, lásd backend
    // schemas/project.veg_datum) - ebből lesz a több napos sáv a naptárban.
    forgatas_datuma_vege: p.veg_datum ?? p.forgatas_datuma_vege,
  }));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <UtomunkaContent
          lejartSzures={szures === "lejart"}
          initialDeliverables={deliverables}
          deliverablesHasMore={deliverables.length === INITIAL_BATCH}
          initialProjects={calendarProjects}
          projectsHasMore={projects.length === INITIAL_BATCH}
          employees={employees}
          statusOptions={statusOptions}
          allapotBeallitasok={allapotBeallitasok}
          kartyaMezok={kartyaMezok}
          vinyoOptions={vinyoReszletes.options}
          vinyoKezelheto={vinyoReszletes.kezelheto}
          isAdmin={szerepkorei(currentUser).includes("admin")}
          // SZÁNDÉKOSAN nem canDoAction: az Utómunkán a backend a szerepkör-
          // kaput kikapcsolta, itt kizárólag a page_permissions dönt - így a
          // vágó szerepkörű, teljes oldal-jogú munkatárs is tud kiosztani és
          // állapotot állítani (lásd lib/permissions.canDoPageAction).
          canCreate={canDoPageAction(pagePermissions, PAGE, "create")}
          canDelete={canDoPageAction(pagePermissions, PAGE, "delete")}
          canEdit={canDoPageAction(pagePermissions, PAGE, "edit")}
        />
      </div>
    </div>
  );
}
