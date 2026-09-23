import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { AdminTanulasVezerlok } from "@/components/admin-agent/AdminTanulasVezerlok";
import { AdminVisszajatszas } from "@/components/admin-agent/AdminVisszajatszas";
import { LaraOnellenorzes } from "@/components/admin-agent/LaraOnellenorzes";
import { getAdminEvaluations, getAdminLearningRuns, getAdminReplaySummary, getMyPagePermissions, getOnellenorzesFutasok } from "@/lib/api";

const PAGE = "/admin-agent";

/** Lara — TANULÁS ÉS MINŐSÉG.
 *
 * A háttér-tanuló futásai (feldolgozott javítások, szabály-/példa-jelöltek,
 * SOP-kérések) és az értékelő futások (biztonsági/pénzügyi invariánsok kóddal).
 * Kattintható eredmények, nem dekoratív animáció. */
export default async function AdminAgentTanulasPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  const canRun = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");

  const [tanulasok, evalok, visszajatszas, onellenorzes] = await Promise.all([
    getAdminLearningRuns(),
    getAdminEvaluations(),
    getAdminReplaySummary(),
    getOnellenorzesFutasok(),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        <div className="flex flex-col gap-4">
          <Card title="Vezérlés">
            <AdminTanulasVezerlok canRun={canRun} />
          </Card>

          <Card title="Lara önellenőrzése — folyamatos tanulás">
            <LaraOnellenorzes kezdo={onellenorzes?.elemek ?? []} canRun={canRun} />
          </Card>

          <Card title="Visszajátszás és találati arány">
            <AdminVisszajatszas kezdo={visszajatszas} canRun={canRun} />
          </Card>

          <Card title="Háttér-tanuló futások">
            {!tanulasok || tanulasok.elemek.length === 0 ? (
              <p className="text-[13px] text-text-secondary">Még nem futott háttér-tanuló.</p>
            ) : (
              <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
                <table className="w-full border-collapse text-[13px]">
                  <thead>
                    <tr className="border-b border-border bg-surface-3 text-left text-text-muted">
                      <th className="px-3 py-2 font-medium">Indító</th>
                      <th className="px-3 py-2 font-medium">Javítás</th>
                      <th className="px-3 py-2 font-medium">Szabály-jelölt</th>
                      <th className="px-3 py-2 font-medium">Példa-jelölt</th>
                      <th className="px-3 py-2 font-medium">SOP-kérés</th>
                      <th className="px-3 py-2 font-medium">Befejezve</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tanulasok.elemek.map((lr) => (
                      <tr key={lr.id} className="border-b border-border last:border-0">
                        <td className="px-3 py-2 text-text-secondary">{lr.trigger}</td>
                        <td className="px-3 py-2 text-text-primary">{lr.feldolgozott_korrekciok}</td>
                        <td className="px-3 py-2 text-text-primary">{lr.uj_szabaly_jeloltek}</td>
                        <td className="px-3 py-2 text-text-primary">{lr.uj_pelda_jeloltek}</td>
                        <td className="px-3 py-2 text-text-primary">{lr.sop_keresek}</td>
                        <td className="px-3 py-2 text-text-muted">
                          {lr.veg_at ? new Date(lr.veg_at).toLocaleString("hu-HU") : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title="Értékelő futások (eval)">
            <p className="mb-3 text-[12px] text-text-muted">
              A beépített biztonsági esetek (pl. banki utalás mindig tiltott, L0-ban nincs végrehajtás): azt igazolja,
              hogy a tanulás nem lazította a korlátokat — ezért kell átmennie élesítés előtt. Azt, hogy Lara
              mennyire talál, a fenti „Találati arány” méri.
            </p>
            {!evalok || evalok.elemek.length === 0 ? (
              <p className="text-[13px] text-text-secondary">Még nem futott értékelés.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {evalok.elemek.map((e) => (
                  <li
                    key={e.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5 text-[13px]"
                  >
                    <span className="text-text-secondary">
                      {e.sikeres}/{e.osszes} sikeres · kritikus hiba: {e.kritikus_hiba}
                      {e.arany !== null ? ` · ${Math.round(e.arany * 100)}%` : ""}
                    </span>
                    <span
                      className={`rounded-[var(--radius)] px-2 py-0.5 text-[12px] font-medium ${
                        e.atment ? "bg-bg-success text-text-success" : "bg-bg-danger text-text-danger"
                      }`}
                    >
                      {e.atment ? "Átment" : "Nem ment át"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
