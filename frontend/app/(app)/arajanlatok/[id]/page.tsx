import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { ArajanlatFulek } from "@/components/arajanlat/ArajanlatFulek";
import { getMyPagePermissions } from "@/lib/api";
import { canDoPageAction, lathatjaAzOldalt } from "@/lib/permissions";
import { AjanlatSzerkeszto } from "@/components/arajanlat/AjanlatSzerkeszto";

const PAGE = "/arajanlatok";

/** Egy árajánlat szerkesztője (a fő képernyő) - lásd AjanlatSzerkeszto. */
export default async function ArajanlatSzerkesztoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const pagePermissions = await getMyPagePermissions();
  if (!lathatjaAzOldalt(pagePermissions, PAGE)) redirect("/nincs-jogosultsag");
  const van = (m: "create" | "edit" | "delete") => canDoPageAction(pagePermissions, PAGE, m);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <ArajanlatFulek />
        <AjanlatSzerkeszto id={Number(id)} canEdit={van("edit")} canCreate={van("create")} canDelete={van("delete")} />
      </div>
    </div>
  );
}
