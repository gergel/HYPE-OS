import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { AdminTudastarKezelo } from "@/components/admin-agent/AdminTudastarKezelo";
import { getAdminMemory, getAdminRules, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

/** ADMIN-ÁGENS — TUDÁSTÁR.
 *
 * Az ügynök tudása: szabályok és példák. A gépi JELÖLT (javításokból, illetve a
 * projektkód/utókövetés megfigyeléséből) egyértelműen elkülönítve jelenik meg,
 * és csak emberi jóváhagyással kerül éles használatba. */
export default async function AdminAgentTudastarPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  const canEdit = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");

  const [szabalyok, peldak] = await Promise.all([getAdminRules(), getAdminMemory()]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        {szabalyok === null || peldak === null ? (
          <Card title="Tudástár">
            <p className="text-[13px] text-text-secondary">A tudástár most nem érhető el.</p>
          </Card>
        ) : (
          <AdminTudastarKezelo
            kezdoSzabalyok={szabalyok.elemek}
            kezdoPeldak={peldak.elemek}
            felretettRegi={peldak.felretett_regi ?? 0}
            tanulasKezdete={peldak.tanulas_kezdete ?? null}
            canEdit={canEdit}
          />
        )}
      </div>
    </div>
  );
}
