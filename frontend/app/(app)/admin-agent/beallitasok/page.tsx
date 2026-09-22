import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { AdminBeallitasok } from "@/components/admin-agent/AdminBeallitasok";
import { getAdminAgentSettings, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

/** ADMIN-ÁGENS — BEÁLLÍTÁSOK.
 *
 * A biztonságos alapállás kapcsolói (modul, mellékhatások, vészleállítás). A
 * magas kockázatú kapcsolók módosításához a legerősebb (delete) művelet-jog
 * kell — a finomabb pénzügyi/jogi/bizalmi beállítások a következő fázis. */
export default async function AdminAgentBeallitasokPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  // A kapcsolók a legerősebb művelet-joghoz kötöttek (a backend "delete"
  // ellenőrzést végez — routes/admin_agent.py settings/pause/resume).
  const canManage = pagePermissions === null || !!pagePermissions[PAGE]?.includes("delete");

  const beallitasok = await getAdminAgentSettings();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        <Card title="Beállítások">
          {beallitasok === null ? (
            <p className="text-[13px] text-text-secondary">
              A beállítások most nem érhetők el. Töltsd újra az oldalt egy kicsit később.
            </p>
          ) : (
            <AdminBeallitasok kezdo={beallitasok} canManage={canManage} />
          )}
        </Card>
      </div>
    </div>
  );
}
