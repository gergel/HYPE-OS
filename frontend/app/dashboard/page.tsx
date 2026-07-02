import { Card } from "@/components/Card";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { formatHuf, getClients, getDashboardSummary, getProjectCodes } from "@/lib/api";

function statusTone(allapot: string | null): "success" | "warning" | "danger" | "neutral" {
  if (!allapot) return "neutral";
  const normalized = allapot.toLowerCase();
  if (["folyamatban", "aktiv", "kesz"].some((s) => normalized.includes(s))) return "success";
  if (["tervezes", "elozetes"].some((s) => normalized.includes(s))) return "warning";
  if (["blokkolva", "lezarva"].some((s) => normalized.includes(s))) return "danger";
  return "neutral";
}

export default async function DashboardPage() {
  const [summary, projectCodes, clients] = await Promise.all([
    getDashboardSummary(),
    getProjectCodes(5),
    getClients(),
  ]);

  const clientNameById = new Map(clients.map((c) => [c.id, c.nev]));
  const apiUnavailable = summary === null;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        {apiUnavailable && (
          <div className="rounded-[var(--radius)] border border-border bg-surface-1 px-4 py-3 text-[13px] text-text-secondary">
            A backend API ({process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}) jelenleg nem elérhető -
            demó/placeholder adatok jelennek meg.
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="Mai forgatás" value={summary?.mai_forgatasok ?? "–"} />
          <StatCard label="Aktív Project Code" value={summary?.aktiv_project_codeok ?? "–"} />
          <StatCard
            label="Equipment ütközés"
            value={summary?.equipment_utkozesek ?? "–"}
            tone={summary && summary.equipment_utkozesek > 0 ? "danger" : "default"}
          />
          <StatCard label="Havi bevétel" value={summary ? formatHuf(summary.havi_bevetel) : "–"} />
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.3fr_1fr]">
          <Card title="Mai diszpó / forgatások">
            <p className="text-[13px] text-text-muted">
              A Naptár / Diszpó modul (Callsheet entitás) még nincs kitöltve adattal - a projektváz kész, a
              lekérdezés a modul UI-jának Fázis 1 munkája.
            </p>
          </Card>
          <Card title="Utómunka állapot">
            <p className="text-[13px] text-text-muted">
              A Deliverable-ök összegzése (kész / folyamatban / lejárt határidő) a Fázis 1 Utómunka modul UI
              munkájának része.
            </p>
          </Card>
        </div>

        <Card title="Aktív Project Code-ok">
          {projectCodes.length === 0 ? (
            <p className="text-[13px] text-text-muted">Még nincs felvett Project Code.</p>
          ) : (
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-1.5 text-left font-medium text-text-secondary">Projektkód</th>
                  <th className="py-1.5 text-left font-medium text-text-secondary">Ügyfél</th>
                  <th className="py-1.5 text-right font-medium text-text-secondary">Becsült profit</th>
                  <th className="py-1.5 text-right font-medium text-text-secondary">Státusz</th>
                </tr>
              </thead>
              <tbody>
                {projectCodes.map((pc) => (
                  <tr key={pc.id} className="border-b border-border last:border-0">
                    <td className="py-2">{pc.projektkod}</td>
                    <td className="py-2 text-text-secondary">{clientNameById.get(pc.client_id) ?? "–"}</td>
                    <td className="py-2 text-right">{formatHuf(pc.becsult_profit)}</td>
                    <td className="py-2 text-right">
                      <StatusBadge label={pc.esemeny_allapota ?? "Nincs státusz"} tone={statusTone(pc.esemeny_allapota)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}
