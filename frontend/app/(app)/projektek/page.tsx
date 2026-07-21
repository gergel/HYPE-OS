import { ProjektekContent } from "@/components/ProjektekContent";
import { TopBar } from "@/components/TopBar";
import { getFieldTypes, getProjectCodes, getProjects } from "@/lib/api";

// Csak ennyi legutóbb módosított/létrehozott projektet töltünk be azonnal
// (a backend list_items alapértelmezetten updated_at szerint csökkenő
// sorrendben ad vissza, lásd api/crud_router.py) - a régebbi, rég lezárt
// projektek a háttérben töltődnek be (lásd ProjektekContent).
const INITIAL_BATCH = 200;

export default async function ProjektekPage() {
  const [projects, projectCodes, fieldTypes] = await Promise.all([
    getProjects(INITIAL_BATCH),
    getProjectCodes(),
    getFieldTypes("project"),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <ProjektekContent
          initialProjects={projects}
          hasMore={projects.length === INITIAL_BATCH}
          projectCodes={projectCodes}
          statusOptions={fieldTypes.allapot?.options ?? []}
        />
      </div>
    </div>
  );
}
