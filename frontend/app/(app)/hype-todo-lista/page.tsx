import { getCurrentUser, getEmployees, getFieldTypes, getHypeTodoItems, getMyPagePermissions } from "@/lib/api";
import { HypeTodoContent } from "@/components/HypeTodoContent";
import { TopBar } from "@/components/TopBar";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/hype-todo-lista";

export default async function HypeTodoListaPage() {
  const [items, fieldTypes, employees, currentUser, pagePermissions] = await Promise.all([
    getHypeTodoItems(),
    getFieldTypes("hypeTodo"),
    getEmployees(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const statusOptions = fieldTypes.allapot?.options ?? [];
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <HypeTodoContent
          items={items}
          employees={employees}
          statusOptions={statusOptions}
          canCreate={canCreate}
          canDelete={canDelete}
          canEdit={canEdit}
        />
      </div>
    </div>
  );
}
