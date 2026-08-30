import { getCurrentUser, getEmployees, getFieldTypes, getFloraFeladatok, getMyPagePermissions } from "@/lib/api";
import { FloraContent } from "@/components/FloraContent";
import { TopBar } from "@/components/TopBar";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/flora";

export default async function FloraPage() {
  const [feladatok, fieldTypes, employees, currentUser, pagePermissions] = await Promise.all([
    getFloraFeladatok(),
    getFieldTypes("floraFeladat"),
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
