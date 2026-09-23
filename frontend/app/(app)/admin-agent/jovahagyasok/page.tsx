import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { AdminJovahagyasok } from "@/components/admin-agent/AdminJovahagyasok";
import { getAdminAgentApprovals, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

/** HYRON — JÓVÁHAGYÁSOK.
 *
 * HYRON által előkészített, ember jóváhagyására váró műveletek. A döntés a
 * konkrét javaslathoz (payload-hash) kötött; a végrehajtás a szerver-oldali
 * guard-láncon (policy, kapcsolók, idempotencia) megy át. */
export default async function AdminAgentJovahagyasokPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  const canDecide = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");

  const adat = await getAdminAgentApprovals();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        <Card title={`Jóváhagyások${adat ? ` (${adat.elemek.length})` : ""}`}>
          {adat === null ? (
            <p className="text-[13px] text-text-secondary">
              A jóváhagyások most nem érhetők el. Töltsd újra az oldalt egy kicsit később.
            </p>
          ) : (
            <AdminJovahagyasok kezdoElemek={adat.elemek} canDecide={canDecide} />
          )}
        </Card>
      </div>
    </div>
  );
}
