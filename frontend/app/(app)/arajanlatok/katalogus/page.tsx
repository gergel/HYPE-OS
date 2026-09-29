import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { ArajanlatFulek } from "@/components/arajanlat/ArajanlatFulek";
import { getMyPagePermissions } from "@/lib/api";
import { canDoPageAction, lathatjaAzOldalt } from "@/lib/permissions";
import { KatalogusSzerkeszto } from "@/components/arajanlat/KatalogusSzerkeszto";

const PAGE = "/arajanlatok";

/** A tétel-katalógus szerkesztője (inline árírás, ártörténet, archiválás). */
export default async function ArajanlatKatalogusPage() {
  const pagePermissions = await getMyPagePermissions();
  if (!lathatjaAzOldalt(pagePermissions, PAGE)) redirect("/nincs-jogosultsag");
  const van = (m: "create" | "edit" | "delete") => canDoPageAction(pagePermissions, PAGE, m);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <ArajanlatFulek />
        <KatalogusSzerkeszto canEdit={van("edit")} />
      </div>
    </div>
  );
}
