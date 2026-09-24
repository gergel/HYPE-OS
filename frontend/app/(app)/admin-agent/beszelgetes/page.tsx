import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { LaraBeszelgetes } from "@/components/admin-agent/LaraBeszelgetes";
import { getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

/** Lara — KÉRDEZZ LARÁTÓL.
 *
 * Kérdezni lehet tőle (csak olvas: a jóváhagyott tudásából és a rendszer
 * adataiból válaszol, és megmutatja, honnan tudja), tanítani (előnézet →
 * mentés), és próbára tenni a tudását (vak jóslat a vizsgaügyeken, saját
 * kérdés elvárt válasszal). */
export default async function LaraBeszelgetesPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  const canEdit = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        <LaraBeszelgetes canEdit={canEdit} />
      </div>
    </div>
  );
}
