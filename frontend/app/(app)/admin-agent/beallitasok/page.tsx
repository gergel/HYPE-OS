import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { AdminBeallitasok } from "@/components/admin-agent/AdminBeallitasok";
import { AdminTrustPolicies } from "@/components/admin-agent/AdminTrustPolicies";
import { getAdminAgentSettings, getAdminTrustPolicies, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

/** HYRON — BEÁLLÍTÁSOK.
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

  const [beallitasok, trustPolicies] = await Promise.all([getAdminAgentSettings(), getAdminTrustPolicies()]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        <div className="flex flex-col gap-4">
          <Card title="Kapcsolók és vészleállítás">
            {beallitasok === null ? (
              <p className="text-[13px] text-text-secondary">
                A beállítások most nem érhetők el. Töltsd újra az oldalt egy kicsit később.
              </p>
            ) : (
              <AdminBeallitasok kezdo={beallitasok} canManage={canManage} />
            )}
          </Card>

          <Card title="Bizalmi szintek (feladattípusonként)">
            {trustPolicies === null ? (
              <p className="text-[13px] text-text-secondary">A bizalmi szintek most nem érhetők el.</p>
            ) : (
              <AdminTrustPolicies kezdo={trustPolicies.elemek} canManage={canManage} />
            )}
          </Card>

          {beallitasok?.integraciok && beallitasok.integraciok.length > 0 && (
            <Card title="Forráskapcsolatok">
              <ul className="flex flex-col gap-2">
                {beallitasok.integraciok.map((i) => {
                  const kesz = i.allapot === "kesz";
                  return (
                    <li key={i.kulcs} className="flex items-start justify-between gap-3 text-[13px]">
                      <div>
                        <p className="text-text-primary">{i.nev}</p>
                        {!kesz && i.uzenet && <p className="text-[12px] text-text-muted">{i.uzenet}</p>}
                      </div>
                      <span
                        className={`shrink-0 rounded-[var(--radius)] px-2 py-0.5 text-[12px] font-medium ${
                          kesz ? "bg-bg-success text-text-success" : "bg-bg-warning text-text-warning"
                        }`}
                      >
                        {kesz ? "Kész" : "Beállítás szükséges"}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
