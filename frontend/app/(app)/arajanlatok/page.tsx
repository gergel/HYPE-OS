import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { ArajanlatFulek } from "@/components/arajanlat/ArajanlatFulek";
import { getMyPagePermissions } from "@/lib/api";
import { canDoPageAction, lathatjaAzOldalt } from "@/lib/permissions";
import { AjanlatLista } from "@/components/arajanlat/AjanlatLista";

const PAGE = "/arajanlatok";

/** Árajánlat-készítő: a lista (szűrőkkel) és az „Új árajánlat” (sablonból
 * vagy üresen). Külön adható oldal-jog: „/arajanlatok”. */
export default async function ArajanlatokPage() {
  const pagePermissions = await getMyPagePermissions();
  if (!lathatjaAzOldalt(pagePermissions, PAGE)) redirect("/nincs-jogosultsag");
  const van = (m: "create" | "edit" | "delete") => canDoPageAction(pagePermissions, PAGE, m);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <ArajanlatFulek />
        <AjanlatLista canCreate={van("create")} canEdit={van("edit")} />
      </div>
    </div>
  );
}
