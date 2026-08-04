import { ProjektekContent } from "@/components/ProjektekContent";
import { TopBar } from "@/components/TopBar";
import { getCurrentUser, getFieldTypes, getMyPagePermissions, getProjectCodes, getProjects } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

// Csak ennyi legutóbb módosított/létrehozott projektet töltünk be azonnal
// (a backend list_items alapértelmezetten updated_at szerint csökkenő
// sorrendben ad vissza, lásd api/crud_router.py) - a régebbi, rég lezárt
// projektek a háttérben töltődnek be (lásd ProjektekContent).
const INITIAL_BATCH = 200;
const PAGE = "/projektek";

export default async function ProjektekPage() {
  const [projects, projectCodes, fieldTypes, currentUser, pagePermissions] = await Promise.all([
    getProjects(INITIAL_BATCH),
    getProjectCodes(),
    getFieldTypes("project"),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <ProjektekContent
          initialProjects={projects}
          hasMore={projects.length === INITIAL_BATCH}
          projectCodes={projectCodes}
          statusOptions={fieldTypes.allapot?.options ?? []}
          canCreate={canDoAction(currentUser?.role, pagePermissions, PAGE, "create")}
          canDelete={canDoAction(currentUser?.role, pagePermissions, PAGE, "delete")}
          canEdit={canDoAction(currentUser?.role, pagePermissions, PAGE, "edit")}
        />
      </div>
    </div>
  );
}
