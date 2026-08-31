import { getEmployees, getFieldTypes, getFloraFeladatok, getMyPagePermissions } from "@/lib/api";
import { FloraContent } from "@/components/FloraContent";
import { TopBar } from "@/components/TopBar";
import { canDoPageAction } from "@/lib/permissions";

const PAGE = "/flora";

export default async function FloraPage() {
  const [feladatok, fieldTypes, employees, pagePermissions] = await Promise.all([
    getFloraFeladatok(),
    getFieldTypes("floraFeladat"),
    getEmployees(),
    getMyPagePermissions(),
  ]);
  const statusOptions = fieldTypes.allapot?.options ?? [];
  // A szerepkör-kapu itt nem érvényes - kizárólag a page_permissions dönt,
  // ugyanúgy, ahogy a backend (lásd routes/flora.py _MINDEN_SZEREPKOR).
  const canCreate = canDoPageAction(pagePermissions, PAGE, "create");
  const canDelete = canDoPageAction(pagePermissions, PAGE, "delete");
  const canEdit = canDoPageAction(pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <FloraContent
          feladatok={feladatok}
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
