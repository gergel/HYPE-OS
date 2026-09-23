import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { LaraKerdesek } from "@/components/admin-agent/LaraKerdesek";
import { getLaraKerdesek, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

/** Lara — KÉRDÉSEK.
 *
 * Lara a háttérben összeveti, mit javasolt volna a rögzített munkára, és mi
 * lett a valóság; ahol nem érti az eltérést, itt kérdez. A válasz tudássá válik. */
export default async function LaraKerdesekPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  const canEdit = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");

  const [nyitott, kesz] = await Promise.all([getLaraKerdesek("nyitott"), getLaraKerdesek("megvalaszolt")]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        {nyitott === null ? (
          <p className="text-[13px] text-text-secondary">A kérdések most nem érhetők el.</p>
        ) : (
          <LaraKerdesek nyitottak={nyitott.elemek} megvalaszoltak={kesz?.elemek ?? []} canEdit={canEdit} />
        )}
      </div>
    </div>
  );
}
