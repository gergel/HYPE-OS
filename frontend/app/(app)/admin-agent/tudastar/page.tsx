import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { getAdminRules, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

const ALLAPOT_CIMKE: Record<string, string> = {
  draft: "Vázlat",
  pending: "Gépi jelölt (jóváhagyásra vár)",
  active: "Aktív",
  retired: "Nyugdíjazott",
};

/** ADMIN-ÁGENS — TUDÁSTÁR.
 *
 * A szabályok és jóváhagyott tudás. A gépi szabályJELÖLT egyértelműen el van
 * különítve az aktív szabálytól (a jelölt nem hat az éles döntésre, amíg ember
 * jóvá nem hagyja és sikeres eval után nem aktiválják). */
export default async function AdminAgentTudastarPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");

  const adat = await getAdminRules();
  const elemek = adat?.elemek ?? [];
  const aktiv = elemek.filter((r) => r.allapot === "active");
  const jelolt = elemek.filter((r) => r.allapot === "pending");
  const egyeb = elemek.filter((r) => r.allapot !== "active" && r.allapot !== "pending");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        {adat === null ? (
          <Card title="Tudástár">
            <p className="text-[13px] text-text-secondary">A tudástár most nem érhető el.</p>
          </Card>
        ) : elemek.length === 0 ? (
          <Card title="Tudástár">
            <div className="rounded-[var(--radius)] border border-dashed border-border px-4 py-8 text-center">
              <p className="text-[13px] text-text-secondary">Még nincs szabály.</p>
              <p className="mt-1 text-[12px] text-text-muted">
                A háttér-tanuló az emberi javításokból készít szabály-jelölteket; ezek itt jelennek meg, és emberi
                jóváhagyás + sikeres értékelés után aktiválhatók.
              </p>
            </div>
          </Card>
        ) : (
          <div className="flex flex-col gap-4">
            <RuleLista cim={`Aktív szabályok (${aktiv.length})`} elemek={aktiv} />
            <RuleLista
              cim={`Gépi jelöltek (${jelolt.length})`}
              elemek={jelolt}
              megjegyzes="Ezek gépi javaslatok emberi jóváhagyásra — nem hatnak az éles döntésre aktiválás előtt."
            />
            {egyeb.length > 0 && <RuleLista cim={`Egyéb (${egyeb.length})`} elemek={egyeb} />}
          </div>
        )}
      </div>
    </div>
  );
}

function RuleLista({
  cim,
  elemek,
  megjegyzes,
}: {
  cim: string;
  elemek: { id: number; hatokor: string; cim: string; tartalom: string; allapot: string; verzio: number }[];
  megjegyzes?: string;
}) {
  return (
    <Card title={cim}>
      {megjegyzes && <p className="mb-3 text-[12px] text-text-muted">{megjegyzes}</p>}
      {elemek.length === 0 ? (
        <p className="text-[13px] text-text-secondary">Nincs elem.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {elemek.map((r) => (
            <li key={r.id} className="rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className="rounded-[var(--radius)] bg-surface-2 px-2 py-0.5 text-[11.5px] text-text-secondary">
                  {r.hatokor}
                </span>
                <span className="text-[13px] font-medium text-text-primary">{r.cim}</span>
                <span className="text-[11.5px] text-text-muted">
                  · {ALLAPOT_CIMKE[r.allapot] ?? r.allapot} · v{r.verzio}
                </span>
              </div>
              <p className="text-[12.5px] text-text-secondary">{r.tartalom}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
