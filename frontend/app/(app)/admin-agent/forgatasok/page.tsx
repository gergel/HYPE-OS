import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { LaraForgatasIsmeret } from "@/components/admin-agent/LaraForgatasIsmeret";
import { getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

/** Lara — FORGATÁS-ISMERET.
 *
 * Melyik korábbi forgatáson mi volt pontosan a feladat, mi ment ki rá
 * ténylegesen, és ebből mit tanult Lara az ilyen feladatokhoz (technikai lista,
 * brief). A `?forgatas=ID` egy forgatást rögtön megnyit (a diszpó-gomb
 * „javítás” linkje). */
export default async function LaraForgatasIsmeretPage({
  searchParams,
}: {
  searchParams: Promise<{ forgatas?: string }>;
}) {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  const canEdit = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");
  const { forgatas } = await searchParams;
  const kezdo = forgatas && /^\d+$/.test(forgatas) ? Number(forgatas) : null;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        <LaraForgatasIsmeret canEdit={canEdit} kezdoForgatas={kezdo} />
      </div>
    </div>
  );
}
