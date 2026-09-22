import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { TIPUS_CIMKE } from "@/components/admin-agent/allapotok";
import { getAdminAgentApprovals, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

type ApprovalSor = {
  approval_id?: number;
  proposal_id?: number;
  task_id?: number;
  tipus?: string;
  eszkoz?: string;
  kockazat?: string;
  cim?: string;
  letrehozva?: string | null;
};

/** ADMIN-ÁGENS — JÓVÁHAGYÁSOK.
 *
 * Az ágens által előkészített, ember jóváhagyására váró műveletek. A
 * jóváhagyás a payload-hoz kötött (payload_hash), a végrehajtás pedig a
 * szerver-oldali policy engine-en megy át. A javaslat-generáló és végrehajtó
 * réteg a következő fázisokban készül el — addig ez a lista üres. */
export default async function AdminAgentJovahagyasokPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");

  const adat = await getAdminAgentApprovals();
  const elemek = (adat?.elemek ?? []) as ApprovalSor[];

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        <Card title={`Jóváhagyások${adat ? ` (${elemek.length})` : ""}`}>
          {adat === null ? (
            <p className="text-[13px] text-text-secondary">
              A jóváhagyások most nem érhetők el. Töltsd újra az oldalt egy kicsit később.
            </p>
          ) : elemek.length === 0 ? (
            <div className="rounded-[var(--radius)] border border-dashed border-border px-4 py-8 text-center">
              <p className="text-[13px] text-text-secondary">Nincs jóváhagyásra váró művelet.</p>
              <p className="mx-auto mt-1 max-w-xl text-[12px] text-text-muted">
                Amikor az ágens éles feladatokon dolgozik, az emberi döntést igénylő műveletek (pl. e-mail kiküldése,
                rekord rögzítése) itt jelennek meg. A jóváhagyás a konkrét művelethez kötött, és a végrehajtás a
                szerver-oldali szabályrendszeren megy át — a jóváhagyás önmagában nem indít külső hívást.
              </p>
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {elemek.map((a) => (
                <li
                  key={a.approval_id ?? `${a.proposal_id}`}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2.5"
                >
                  <div>
                    <p className="text-[13px] font-medium text-text-primary">{a.cim ?? `Feladat #${a.task_id}`}</p>
                    <p className="text-[12px] text-text-muted">
                      {(a.tipus && TIPUS_CIMKE[a.tipus]) ?? a.tipus ?? "—"}
                      {a.eszkoz ? ` · ${a.eszkoz}` : ""}
                    </p>
                  </div>
                  {a.kockazat && (
                    <span className="rounded-[var(--radius)] bg-bg-warning px-2 py-0.5 text-[12px] font-medium text-text-warning">
                      {a.kockazat}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
