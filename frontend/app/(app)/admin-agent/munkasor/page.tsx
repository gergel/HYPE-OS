import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { AdminMunkasor } from "@/components/admin-agent/AdminMunkasor";
import { getAdminTasks, getEmployees, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

/** Lara — MUNKASOR.
 *
 * Lara és az emberek közös feladatlistája. Belső munkaszervezés: itt a
 * feladat-létrehozás, felelős-kiosztás és a mellékhatás-mentes állapotváltás
 * történik. A javaslat-generálás és a végrehajtás a következő fázisokban
 * kapcsolódik be — addig minden feladat L0 (árnyék). */
export default async function AdminAgentMunkasorPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  const canCreate = pagePermissions === null || !!pagePermissions[PAGE]?.includes("create");
  const canEdit = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");

  const [lista, emberek] = await Promise.all([getAdminTasks(), getEmployees()]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        <Card title={`Munkasor${lista ? ` (${lista.osszesen})` : ""}`}>
          {lista === null ? (
            <p className="text-[13px] text-text-secondary">
              A munkasor most nem érhető el. Töltsd újra az oldalt egy kicsit később.
            </p>
          ) : (
            <AdminMunkasor
              kezdoElemek={lista.elemek}
              emberek={emberek.map((e) => ({ id: e.id, nev: e.full_name }))}
              canCreate={canCreate}
              canEdit={canEdit}
            />
          )}
        </Card>
      </div>
    </div>
  );
}
