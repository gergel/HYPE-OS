import Link from "next/link";
import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { AdminJavaslatSzerkeszto } from "@/components/admin-agent/AdminJavaslatSzerkeszto";
import { AdminTaskActions } from "@/components/admin-agent/AdminTaskActions";
import { ALLAPOT_CIMKE, TIPUS_CIMKE } from "@/components/admin-agent/allapotok";
import { type AdminTaskTimeline, getAdminTaskTimeline, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

const SZEREPLO_CIMKE: Record<string, string> = { agent: "HYRON", human: "Ember", system: "Rendszer" };

/** HYRON — FELADAT RÉSZLETEK / IDŐVONAL.
 *
 * Egy feladat teljes, olvasható története: mit elemzett HYRON, milyen
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
  const canEdit = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");

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

            <Card title="Műveletek">
              <AdminTaskActions
                taskId={adat.task.id}
                tipus={adat.task.tipus}
                proposals={adat.proposals
                  .filter((p) => p.allapot === "ready" || p.allapot === "draft")
                  .map((p) => ({ id: p.id, eszkoz: p.eszkoz }))}
                canEdit={canEdit}
              />
            </Card>

            <Card title="Javaslatok">
              {adat.proposals.length === 0 ? (
                <p className="text-[13px] text-text-secondary">
                  Ehhez a feladathoz még nincs javaslat.
                  {["tig", "szerzodes", "email"].includes(adat.task.tipus) &&
                    " A „Tervezet készítése (HYRON)” gombbal kérhetsz egyet."}
                </p>
              ) : (
                <ul className="flex flex-col gap-3">
                  {adat.proposals.map((p) => (
                    <JavaslatKartya key={p.id} p={p} taskId={adat.task.id} canEdit={canEdit} />
                  ))}
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
                  {adat.runs.length} HYRON-futás · legutóbbi:{" "}
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

type Javaslat = AdminTaskTimeline["proposals"][number];

const JAVASLAT_ALLAPOT: Record<string, { cimke: string; osztaly: string }> = {
  ready: { cimke: "Kész javaslat", osztaly: "bg-bg-success text-text-success" },
  draft: { cimke: "Hiányos — pótolni kell", osztaly: "bg-bg-warning text-text-warning" },
  superseded: { cimke: "Leváltva", osztaly: "bg-surface-2 text-text-muted" },
  consumed: { cimke: "Végrehajtva", osztaly: "bg-bg-accent text-text-accent" },
  expired: { cimke: "Lejárt", osztaly: "bg-surface-2 text-text-muted" },
};

const ESZKOZ_CIMKE: Record<string, string> = {
  "szamla_erkeztetes.jovahagy": "Számla felvezetése kiadásként",
  "email.valasz_kuldes": "E-mail kiküldése",
  "tig.piszkozat_mentes": "TIG-piszkozatok mentése (kiküldés nélkül)",
  "szerzodes.piszkozat_mentes": "Szerződés-piszkozatok mentése (kiküldés nélkül)",
};

function penz(v: unknown): string {
  return typeof v === "number" ? `${v.toLocaleString("hu-HU")} Ft` : v ? String(v) : "—";
}

function htmlSzoveg(h: string): string {
  return h.replace(/<br\s*\/?>/gi, "\n").replace(/<\/p>/gi, "\n\n").replace(/<[^>]+>/g, "").trim();
}

function JavaslatKartya({ p, taskId, canEdit }: { p: Javaslat; taskId: number; canEdit: boolean }) {
  const ell = (p.ellenorzesek ?? {}) as {
    hianyok?: string[];
    kapcsolodo_tudas?: {
      szabalyok?: { id: number; cim: string }[];
      hasonlo_esetek?: { id: number; tartalom: string }[];
    };
    modell?: {
      hasznalt?: boolean;
      allapot?: string;
      uzenet?: string;
      osszefoglalo?: string | null;
      indoklas?: string | null;
      bizonytalansag?: number | null;
      hianyzo_adatok?: string[];
      figyelmeztetesek?: string[];
      konfliktus?: string | null;
    };
  };
  const aktiv = p.allapot === "ready" || p.allapot === "draft";
  const all = JAVASLAT_ALLAPOT[p.allapot] ?? { cimke: p.allapot, osztaly: "bg-surface-2 text-text-muted" };
  const payload = p.payload as Record<string, unknown>;
  const tetelek = Array.isArray(payload.tetelek)
    ? (payload.tetelek as { nev?: string; project_nev?: string; mezok?: Record<string, unknown>; forrasok?: Record<string, string> }[])
    : null;
  const tudas = ell.kapcsolodo_tudas;
  const m = ell.modell;

  return (
    <li className={`rounded-[var(--radius)] border border-border bg-surface-3 p-3 ${aktiv ? "" : "opacity-60"}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className={`rounded-[var(--radius)] px-2 py-0.5 text-[12px] font-medium ${all.osztaly}`}>{all.cimke}</span>
        <span className="text-[13px] font-medium text-text-primary">{ESZKOZ_CIMKE[p.eszkoz] ?? p.eszkoz}</span>
        <span className="text-[12px] text-text-muted">· kockázat {p.kockazat}</span>
        {p.jovahagyas_allapot && <span className="text-[12px] text-text-muted">· jóváhagyás: {p.jovahagyas_allapot}</span>}
      </div>

      {aktiv && (
        <p className="mb-2 rounded-[var(--radius)] bg-surface-2 px-2.5 py-1.5 text-[12px] text-text-secondary">
          Ez még csak javaslat — élesben semmi nem történt. Végrehajtás csak jóváhagyás után, a beállított
          bizalmi szinten; kiküldés és aláírás mindig emberi lépés.
        </p>
      )}

      {ell.hianyok && ell.hianyok.length > 0 && (
        <ul className="mb-2 list-inside list-disc text-[12px] text-text-warning">
          {ell.hianyok.map((h, i) => (
            <li key={i}>{h}</li>
          ))}
        </ul>
      )}

      {m && (m.hasznalt || m.allapot) && (
        <div className="mb-2 rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-2 text-[12px]">
          <p className="mb-1 font-medium text-text-primary">HYRON értékelése</p>
          {m.hasznalt ? (
            <div className="flex flex-col gap-1 text-text-secondary">
              {m.osszefoglalo && <p>{m.osszefoglalo}</p>}
              {m.indoklas && (
                <p>
                  <span className="text-text-muted">Indoklás:</span> {m.indoklas}
                </p>
              )}
              {typeof m.bizonytalansag === "number" && (
                <p>
                  <span className="text-text-muted">Bizonytalanság:</span> {Math.round(m.bizonytalansag * 100)}%
                </p>
              )}
              {m.konfliktus && <p className="text-text-warning">{m.konfliktus}</p>}
              {(m.hianyzo_adatok ?? []).length > 0 && (
                <p>
                  <span className="text-text-muted">Hiányzó adatok:</span> {(m.hianyzo_adatok ?? []).join("; ")}
                </p>
              )}
              {(m.figyelmeztetesek ?? []).map((f, i) => (
                <p key={i} className="text-text-warning">
                  {f}
                </p>
              ))}
            </div>
          ) : (
            <p className="text-text-muted">
              {m.allapot === "beallitas_szukseges"
                ? "A modell nincs beállítva (GEMINI_API_KEY) — a javaslat a rendszer ismert adataiból készült."
                : m.allapot === "hiba"
                  ? "A modell most nem válaszolt — a javaslat a rendszer ismert adataiból készült."
                  : "Ehhez a javaslathoz nem kellett modell."}
            </p>
          )}
        </div>
      )}

      {tudas && (
        <div className="mb-2 rounded-[var(--radius)] border border-border bg-surface-2 px-2.5 py-2">
          <p className="mb-1 text-[12px] font-medium text-text-primary">Felhasznált megtanult tudás</p>
          {(tudas.szabalyok ?? []).length === 0 && (tudas.hasonlo_esetek ?? []).length === 0 ? (
            <p className="text-[12px] text-text-muted">
              Ehhez a típushoz / partnerhez még nincs jóváhagyott szabály vagy korábbi eset (Tudástár).
            </p>
          ) : (
            <ul className="flex flex-col gap-1 text-[12px] text-text-secondary">
              {(tudas.szabalyok ?? []).map((sz) => (
                <li key={`s${sz.id}`}>
                  <span className="text-text-muted">Szabály:</span> {sz.cim}
                </li>
              ))}
              {(tudas.hasonlo_esetek ?? []).map((e) => (
                <li key={`e${e.id}`}>
                  <span className="text-text-muted">Hasonló eset:</span> {e.tartalom}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {tetelek ? (
        <div className="overflow-x-auto rounded-[var(--radius)] border border-border">
          <table className="w-full border-collapse text-[12px]">
            <thead>
              <tr className="border-b border-border bg-surface-2 text-left text-text-muted">
                <th className="px-2 py-1.5 font-medium">Fél</th>
                <th className="px-2 py-1.5 font-medium">Projekt</th>
                <th className="px-2 py-1.5 font-medium">Megbízás tárgya</th>
                <th className="px-2 py-1.5 font-medium">Nettó</th>
                <th className="px-2 py-1.5 font-medium">Teljesítés</th>
              </tr>
            </thead>
            <tbody>
              {tetelek.map((t, i) => {
                const f = t.forrasok ?? {};
                const cella = (mezo: string, ertek: string) => (
                  <td className="px-2 py-1.5 align-top" title={f[mezo] ? `forrás: ${f[mezo]}` : "hiányzik"}>
                    {ertek === "—" ? <span className="text-text-warning">hiányzik</span> : <span className="text-text-primary">{ertek}</span>}
                    {f[mezo] && <span className="block text-[10.5px] text-text-muted">{f[mezo]}</span>}
                  </td>
                );
                return (
                  <tr key={i} className="border-b border-border last:border-0">
                    <td className="px-2 py-1.5 align-top text-text-primary">
                      {String(t.mezok?.ceg_neve ?? t.nev ?? "—")}
                    </td>
                    <td className="px-2 py-1.5 align-top text-text-secondary">{t.project_nev ?? "—"}</td>
                    {cella("megbizas_targya", String(t.mezok?.megbizas_targya ?? "—"))}
                    {cella("netto_osszeg", penz(t.mezok?.netto_osszeg))}
                    {cella("teljesites_szoveg", String(t.mezok?.teljesites_szoveg ?? "—"))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : typeof payload.html_body === "string" ? (
        <div className="rounded-[var(--radius)] border border-border bg-surface-2 p-2.5 text-[12.5px]">
          <p className="text-text-muted">
            Címzett: <span className="text-text-primary">{(payload.to as string[] | undefined)?.join(", ") || "— nincs —"}</span>
          </p>
          <p className="mb-2 text-text-muted">
            Tárgy: <span className="text-text-primary">{String(payload.subject ?? "")}</span>
          </p>
          <p className="whitespace-pre-wrap text-text-secondary">{htmlSzoveg(payload.html_body)}</p>
        </div>
      ) : null}

      <details className="mt-2">
        <summary className="cursor-pointer text-[11.5px] text-text-muted">Nyers adat</summary>
        <pre className="mt-1 overflow-x-auto rounded-[var(--radius)] bg-surface-2 p-2.5 text-[11px] text-text-secondary">
          {JSON.stringify(p.payload, null, 2)}
        </pre>
        <p className="mt-1 text-[11px] text-text-muted">payload-ujjlenyomat: {p.payload_hash.slice(0, 16)}…</p>
      </details>

      {aktiv && canEdit && <AdminJavaslatSzerkeszto taskId={taskId} proposalId={p.id} payload={payload} />}
    </li>
  );
}
