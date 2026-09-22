import Link from "next/link";
import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { ALLAPOT_CIMKE, TIPUS_CIMKE } from "@/components/admin-agent/allapotok";
import { getAdminTaskTimeline, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

const SZEREPLO_CIMKE: Record<string, string> = { agent: "Ágens", human: "Ember", system: "Rendszer" };

/** ADMIN-ÁGENS — FELADAT RÉSZLETEK / IDŐVONAL.
 *
 * Egy feladat teljes, olvasható története: mit elemzett az ágens, milyen
 * policy-döntés született, és milyen műveletet JAVASOLNA. Árnyék (L0) módban a
 * javaslat nem hajtódik végre — ezt a lap egyértelműen jelzi. */
export default async function AdminAgentTaskReszletPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const [{ id }, pagePermissions] = await Promise.all([params, getMyPagePermissions()]);
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");

  const taskId = Number(id);
  const adat = Number.isFinite(taskId) ? await getAdminTaskTimeline(taskId) : null;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />
        <Link href="/admin-agent/munkasor" className="mb-4 inline-block text-[13px] text-text-accent hover:underline">
          ← Vissza a munkasorhoz
        </Link>

        {adat === null ? (
          <Card title="Feladat">
            <p className="text-[13px] text-text-secondary">A feladat nem található, vagy nem érhető el.</p>
          </Card>
        ) : (
          <div className="flex flex-col gap-4">
            <Card title={adat.task.cim}>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-[13px] sm:grid-cols-4">
                <Mezo cimke="Típus" ertek={TIPUS_CIMKE[adat.task.tipus] ?? adat.task.tipus} />
                <Mezo cimke="Állapot" ertek={ALLAPOT_CIMKE[adat.task.allapot] ?? adat.task.allapot} />
                <Mezo cimke="Kockázat" ertek={adat.task.kockazat ?? "—"} />
                <Mezo cimke="Bizalmi szint" ertek={adat.task.trust_level} />
                {adat.task.partner_nev && <Mezo cimke="Partner" ertek={adat.task.partner_nev} />}
                {adat.task.altipus && <Mezo cimke="Altípus" ertek={adat.task.altipus} />}
              </dl>
              {adat.task.blokkolo_ok && (
                <div className="mt-3 rounded-[var(--radius)] bg-surface-3 px-3 py-2 text-[12.5px] text-text-secondary">
                  {adat.task.blokkolo_ok}
                </div>
              )}
            </Card>

            <Card title="Javaslatok">
              {adat.proposals.length === 0 ? (
                <p className="text-[13px] text-text-secondary">Ehhez a feladathoz még nincs művelet-javaslat.</p>
              ) : (
                <ul className="flex flex-col gap-3">
                  {adat.proposals.map((p) => {
                    const ell = (p.ellenorzesek ?? {}) as { rendben?: boolean; hianyok?: string[] };
                    return (
                      <li key={p.id} className="rounded-[var(--radius)] border border-border bg-surface-3 p-3">
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <span className="rounded-[var(--radius)] bg-bg-warning px-2 py-0.5 text-[12px] font-medium text-text-warning">
                            {p.kockazat}
                          </span>
                          <span className="text-[13px] font-medium text-text-primary">{p.eszkoz}</span>
                          <span className="text-[12px] text-text-muted">· {p.allapot}</span>
                          {p.jovahagyas_allapot && (
                            <span className="text-[12px] text-text-muted">· jóváhagyás: {p.jovahagyas_allapot}</span>
                          )}
                        </div>
                        <div className="mb-2 rounded-[var(--radius)] bg-bg-accent px-2.5 py-1.5 text-[12px] text-text-accent">
                          Árnyék (L0): ez a javaslat NEM hajtódott végre. A tényleges rögzítés a meglévő pénzügyi
                          folyamaton, emberi jóváhagyással történik.
                        </div>
                        {ell.hianyok && ell.hianyok.length > 0 && (
                          <ul className="mb-2 list-inside list-disc text-[12px] text-text-warning">
                            {ell.hianyok.map((h, i) => (
                              <li key={i}>{h}</li>
                            ))}
                          </ul>
                        )}
                        <pre className="overflow-x-auto rounded-[var(--radius)] bg-surface-2 p-2.5 text-[11.5px] text-text-secondary">
                          {JSON.stringify(p.payload, null, 2)}
                        </pre>
                        <p className="mt-1 text-[11px] text-text-muted">payload-ujjlenyomat: {p.payload_hash.slice(0, 16)}…</p>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>

            <Card title="Idővonal">
              {adat.traces.length === 0 ? (
                <p className="text-[13px] text-text-secondary">Még nincs nyomvonal-bejegyzés.</p>
              ) : (
                <ol className="flex flex-col gap-2">
                  {adat.traces.map((tr) => (
                    <li key={tr.id} className="flex items-start gap-3 text-[13px]">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-text-muted" aria-hidden />
                      <div className="min-w-0">
                        <p className="text-text-primary">
                          <span className="text-text-muted">{SZEREPLO_CIMKE[tr.szereplo] ?? tr.szereplo}:</span>{" "}
                          {tr.muvelet}
                          {tr.eredmeny && <span className="text-text-muted"> → {tr.eredmeny}</span>}
                        </p>
                        {tr.tortent_at && (
                          <p className="text-[11.5px] text-text-muted">
                            {new Date(tr.tortent_at).toLocaleString("hu-HU")}
                            {tr.eroforras ? ` · ${tr.eroforras}` : ""}
                          </p>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              )}
              {adat.runs.length > 0 && (
                <p className="mt-3 text-[11.5px] text-text-muted">
                  {adat.runs.length} ügynökfutás · legutóbbi:{" "}
                  {adat.runs[adat.runs.length - 1].provider ?? "—"} ({adat.runs[adat.runs.length - 1].allapot})
                </p>
              )}
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

function Mezo({ cimke, ertek }: { cimke: string; ertek: string }) {
  return (
    <div>
      <dt className="text-[11.5px] text-text-muted">{cimke}</dt>
      <dd className="text-text-primary">{ertek}</dd>
    </div>
  );
}
