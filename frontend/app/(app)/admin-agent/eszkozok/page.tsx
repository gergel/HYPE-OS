import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { LaraEszkozIsmeret } from "@/components/admin-agent/LaraEszkozIsmeret";
import { getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

/** Lara — ESZKÖZ-ISMERET.
 *
 * Mi micsoda a technikai listán és mire jó: szerep, altípus, gyújtótáv,
 * fényerő, bajonett és a hasonló (helyettesítésre alkalmas) eszközök. A profil
 * szabály alapú, a modell pontosíthatja, az ember javíthatja (az a legerősebb). */
export default async function LaraEszkozIsmeretPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  const canEdit = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        <LaraEszkozIsmeret canEdit={canEdit} />
      </div>
    </div>
  );
}
