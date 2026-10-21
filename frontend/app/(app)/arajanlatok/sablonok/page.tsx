import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { ArajanlatFulek } from "@/components/arajanlat/ArajanlatFulek";
import { getMyPagePermissions } from "@/lib/api";
import { canDoPageAction, lathatjaAzOldalt } from "@/lib/permissions";
import { SablonSzerkeszto } from "@/components/arajanlat/SablonSzerkeszto";

const PAGE = "/arajanlatok";

/** Az ajánlat-sablonok szerkesztője. */
export default async function ArajanlatSablonokPage() {
  const pagePermissions = await getMyPagePermissions();
  if (!lathatjaAzOldalt(pagePermissions, PAGE)) redirect("/nincs-jogosultsag");
  const van = (m: "create" | "edit" | "delete") => canDoPageAction(pagePermissions, PAGE, m);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <ArajanlatFulek />
        <SablonSzerkeszto canEdit={van("edit")} canCreate={van("create")} />
      </div>
    </div>
  );
}
