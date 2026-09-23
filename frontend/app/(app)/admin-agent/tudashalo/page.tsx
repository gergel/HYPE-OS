import { redirect } from "next/navigation";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { Tudashalo } from "@/components/admin-agent/Tudashalo";
import { getAdminKnowledgeGraph, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

/** HYRON — TUDÁSHÁLÓ.
 *
 * A megtanult tudás kapcsolati „glóriája": minden pont egy dolog, amiről
 * HYRON tud (partner, projektkód, számla-cél, szabály, témakör), minden vonal
 * egy kapcsolat. A pont annál nagyobb, minél több kapcsolata van; a vonal annál
 * vastagabb, minél biztosabb a kapcsolat. Lejátszható, hogyan nőtt a tudás. */
export default async function AdminAgentTudashaloPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");

  const graf = await getAdminKnowledgeGraph();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        {graf === null ? (
          <p className="text-[13px] text-text-secondary">A tudásháló most nem érhető el.</p>
        ) : (
          <Tudashalo adat={graf} />
        )}
      </div>
    </div>
  );
}
