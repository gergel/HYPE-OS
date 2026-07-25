import { TopBar } from "@/components/TopBar";
import { UtomunkaContent } from "@/components/deliverable/UtomunkaContent";
import { getCurrentUser, getDeliverables, getEmployees, getFieldTypes, getMyPagePermissions, getProjects, getVinyoOptions } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

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
export default async function UtomunkaPage() {
  const [deliverables, employees, projects, fieldTypes, vinyoOptions, currentUser, pagePermissions] = await Promise.all([
    getDeliverables(INITIAL_BATCH),
    getEmployees(),
    getProjects(INITIAL_BATCH),
    getFieldTypes("deliverable"),
    getVinyoOptions(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);

  const statusOptions = fieldTypes.allapot?.options ?? [];
  const calendarProjects = projects.map((p) => ({
    id: p.id,
    nev: p.nev,
    forgatas_datuma: p.forgatas_datuma,
    forgatas_datuma_vege: p.forgatas_datuma_vege,
  }));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <UtomunkaContent
          initialDeliverables={deliverables}
          deliverablesHasMore={deliverables.length === INITIAL_BATCH}
          initialProjects={calendarProjects}
          projectsHasMore={projects.length === INITIAL_BATCH}
          employees={employees}
          statusOptions={statusOptions}
          vinyoOptions={vinyoOptions}
          canCreate={canDoAction(currentUser?.role, pagePermissions, PAGE, "create")}
          canDelete={canDoAction(currentUser?.role, pagePermissions, PAGE, "delete")}
          canEdit={canDoAction(currentUser?.role, pagePermissions, PAGE, "edit")}
        />
      </div>
    </div>
  );
}
