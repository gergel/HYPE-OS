import { TopBar } from "@/components/TopBar";
import { MunkafelajanlasContent } from "@/components/MunkafelajanlasContent";
import { getEmployees, getMunkafelajanlasok, getMyPagePermissions } from "@/lib/api";
import { canDoPageAction } from "@/lib/permissions";

const PAGE = "/munkafelajanlasok";

/** MUNKAFELAJÁNLÁSOK: ajánlatkérések külsősöknek. A folyamat: feladat ->
 * meghívottak -> személyre szóló ajánlatkérő e-mailek -> árajánlatok a
 * válaszadási határidőig -> BELSŐ kiválasztás a határidő után -> értesítések.
 * Senki nem kapja meg automatikusan a munkát (lásd backend
 * models/munkafelajanlas.py). */
export default async function MunkafelajanlasokPage() {
  const [ajanlatkeresek, employees, pagePermissions] = await Promise.all([
    getMunkafelajanlasok(),
    getEmployees(),
    getMyPagePermissions(),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <MunkafelajanlasContent
          kezdeti={ajanlatkeresek}
          employees={employees}
          canCreate={canDoPageAction(pagePermissions, PAGE, "create")}
          canEdit={canDoPageAction(pagePermissions, PAGE, "edit")}
          canDelete={canDoPageAction(pagePermissions, PAGE, "delete")}
        />
      </div>
    </div>
  );
}
