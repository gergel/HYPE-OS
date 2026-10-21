import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { getAdminAudit, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

const SZEREPLO_CIMKE: Record<string, string> = { agent: "Lara", human: "Ember", system: "Rendszer" };

/** Lara — NAPLÓ (auditnyomvonal).
 *
 * Append-only: az alkalmazásszerepkör nem törölheti, csak olvasható. Minden
 * elemzés, policy-döntés és végrehajtás nyoma itt látszik. */
export default async function AdminAgentNaploPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");

  const adat = await getAdminAudit("?limit=200");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        <Card title={`Napló${adat ? ` (${adat.osszesen})` : ""}`}>
          {adat === null ? (
            <p className="text-[13px] text-text-secondary">A napló most nem érhető el.</p>
          ) : adat.elemek.length === 0 ? (
            <div className="rounded-[var(--radius)] border border-dashed border-border px-4 py-8 text-center">
              <p className="text-[13px] text-text-secondary">Még nincs naplóbejegyzés.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
              <table className="w-full border-collapse text-[13px]">
                <thead>
                  <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                    <th className="px-3 py-2 font-medium">Idő</th>
                    <th className="px-3 py-2 font-medium">Szereplő</th>
                    <th className="px-3 py-2 font-medium">Művelet</th>
                    <th className="px-3 py-2 font-medium">Erőforrás</th>
                    <th className="px-3 py-2 font-medium">Eredmény</th>
                    <th className="px-3 py-2 font-medium">Feladat</th>
                  </tr>
                </thead>
                <tbody>
                  {adat.elemek.map((a) => (
                    <tr key={a.id} className="border-b border-border last:border-0">
                      <td className="px-3 py-2 text-text-muted">
                        {a.tortent_at ? new Date(a.tortent_at).toLocaleString("hu-HU") : "—"}
                      </td>
                      <td className="px-3 py-2 text-text-secondary">{SZEREPLO_CIMKE[a.szereplo] ?? a.szereplo}</td>
                      <td className="px-3 py-2 text-text-primary">{a.muvelet}</td>
                      <td className="px-3 py-2 text-text-secondary">{a.eroforras ?? "—"}</td>
                      <td className="px-3 py-2 text-text-secondary">{a.eredmeny ?? "—"}</td>
                      <td className="px-3 py-2 text-text-muted">
                        {a.task_id ? (
                          <a href={`/admin-agent/munkasor/${a.task_id}`} className="text-text-accent hover:underline">
                            #{a.task_id}
                          </a>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
