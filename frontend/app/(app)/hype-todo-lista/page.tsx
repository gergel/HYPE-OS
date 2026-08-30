import {
  getCurrentUser,
  getEmployees,
  getFieldTypes,
  getHypeTodoItems,
  getLathatjakAzOldalt,
  getMyPagePermissions,
} from "@/lib/api";
import { HypeTodoContent } from "@/components/HypeTodoContent";
import { TopBar } from "@/components/TopBar";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/hype-todo-lista";

export default async function HypeTodoListaPage() {
  const [items, fieldTypes, employees, currentUser, pagePermissions, lathatjakIds] = await Promise.all([
    getHypeTodoItems(),
    getFieldTypes("hypeTodo"),
    getEmployees(),
    getCurrentUser(),
    getMyPagePermissions(),
    getLathatjakAzOldalt(PAGE),
  ]);
  const statusOptions = fieldTypes.allapot?.options ?? [];
  const kategoriaOptions = fieldTypes.kategoria?.options ?? [];
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  // Felelősnek csak az választható, aki ténylegesen látja ezt az oldalt
  // (lásd getLathatjakAzOldalt) - a már hozzárendelt, de időközben
  // jogosultságot vesztett emberek NEVÉT továbbra is az összes `employees`
  // listából oldjuk fel, csak ÚJ hozzárendelésre nem kínáljuk fel őket.
  const lathatjakSet = new Set(lathatjakIds);
  const assignableEmployees = employees.filter((e) => lathatjakSet.has(e.id));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <HypeTodoContent
          items={items}
          employees={employees}
          assignableEmployees={assignableEmployees}
          statusOptions={statusOptions}
          kategoriaOptions={kategoriaOptions}
          canCreate={canCreate}
          canDelete={canDelete}
          canEdit={canEdit}
        />
      </div>
    </div>
  );
}
