import { TopBar } from "@/components/TopBar";
import { ArajanlatokContent } from "@/components/arajanlat/ArajanlatokContent";
import { getArajanlatTetelek, getArajanlatok, getMyPagePermissions } from "@/lib/api";
import { canDoPageAction } from "@/lib/permissions";

const PAGE = "/arajanlatok";

/** Árajánlat-készítő (a felhasználó kérése): külön oldal, KÜLÖN adható
 * hozzáféréssel - alap tétel-katalógussal, visszahívható sablonokkal és
 * HYPE/ContentBee kapcsolóval. A backend itt a szerepkör-kaput kikapcsolta
 * (write_roles = minden szerepkör, lásd routes/arajanlatok.py), ezért a
 * gombok is a canDoPageAction-nel dőlnek el, nem a canDoAction-nel. */
export default async function ArajanlatokPage() {
  const [ajanlatok, tetelek, pagePermissions] = await Promise.all([
    getArajanlatok(),
    getArajanlatTetelek(),
    getMyPagePermissions(),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <ArajanlatokContent
          ajanlatok={ajanlatok}
          tetelek={tetelek}
          canEdit={canDoPageAction(pagePermissions, PAGE, "edit")}
          canCreate={canDoPageAction(pagePermissions, PAGE, "create")}
          canDelete={canDoPageAction(pagePermissions, PAGE, "delete")}
        />
      </div>
    </div>
  );
}
