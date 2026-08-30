import {
  getAgiTodoItems,
  getAllapotBeallitasok,
  getCurrentUser,
  getDeliverables,
  getFieldTypes,
  getMyPagePermissions,
  getProjects,
} from "@/lib/api";
import { AgiContent } from "@/components/AgiContent";
import { TopBar } from "@/components/TopBar";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/agi";

export default async function AgiPage() {
  const [
    items,
    fieldTypes,
    currentUser,
    pagePermissions,
    deliverables,
    deliverableFieldTypes,
    allapotBeallitasok,
    projects,
  ] = await Promise.all([
    getAgiTodoItems(),
    getFieldTypes("agiTodo"),
    getCurrentUser(),
    getMyPagePermissions(),
    getDeliverables(5000),
    getFieldTypes("deliverable"),
    getAllapotBeallitasok(),
    getProjects(5000),
  ]);
  const statusOptions = fieldTypes.allapot?.options ?? [];
  const deliverableStatusOptions = deliverableFieldTypes.allapot?.options ?? [];
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        <AgiContent
          items={items}
          statusOptions={statusOptions}
          canCreate={canCreate}
          canDelete={canDelete}
          canEdit={canEdit}
          deliverables={deliverables}
          deliverableStatusOptions={deliverableStatusOptions}
          allapotBeallitasok={allapotBeallitasok}
          projects={projects}
        />
      </div>
    </div>
  );
}
