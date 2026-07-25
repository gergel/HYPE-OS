"use client";

import { Fragment, useMemo, useState } from "react";
import { ActionButton } from "@/components/ActionButton";
import { Card } from "@/components/Card";
import { ForgatasokCalendar } from "@/components/deliverable/ForgatasokCalendar";
import { ProjectDetailModal } from "@/components/ProjectDetailModal";
import { RowLink } from "@/components/RowLink";
import { StatusBadge } from "@/components/StatusBadge";
import type { Project, ProjectCode } from "@/lib/api";

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

/** YYYY-MM-DD, helyi időzóna szerint (nem UTC - a Date#toISOString() a
 * szerver/böngésző UTC-eltolása miatt éjfél körül átcsúsztatná a "ma"
 * dátumát). */
function localISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatGroupDateLabel(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("hu-HU", { month: "long", day: "numeric", weekday: "long" });
}

/** A Naptár/Diszpó oldal tényleges tartalma - a Project rekordokon
 * ténylegesen tárolt diszpó-állapotot (diszpo/elozetes_diszpo_kuldes,
 * lásd backend/app/services/dispo.py) mutatja meg táblázat/naptár nézetben,
 * a két meglévő küldés-végpontra (POST .../diszpo/elozetes, .../diszpo/kuldes)
 * mutató gombokkal - ugyanazok az akciók, amik eddig csak a Projekt
 * részletnézet "Diszpó küldése" fülén voltak elérhetők, itt viszont egy
 * helyen, az ÖSSZES forgatásra rálátva, hogy ne kelljen projektenként
 * külön-külön benyitni csak azért, hogy admin lássa, kinek van még hátra a
 * diszpója. Csak azok a projektek jelennek meg, amiknek van forgatás
 * dátuma - diszpó csak ezekhez értelmezhető. */
export function NaptarDiszpoContent({
  projects,
  projectCodes,
  canSend,
}: {
  projects: Project[];
  projectCodes: ProjectCode[];
  canSend: boolean;
}) {
  const [view, setView] = useState<"table" | "calendar">("table");
  const [query, setQuery] = useState("");
  const [modalProjectId, setModalProjectId] = useState<number | null>(null);

  const projectCodeById = new Map(projectCodes.map((pc) => [pc.id, pc.projektkod]));

  const scheduled = useMemo(() => projects.filter((p) => p.forgatas_datuma !== null), [projects]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return scheduled;
    return scheduled.filter((p) => {
      const code = projectCodeById.get(p.project_code_id) ?? "";
      const haystack = `${JSON.stringify(p)} ${code}`.toLowerCase();
      return haystack.includes(needle);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scheduled, query, projectCodes]);

  // Csak a tegnapi és a jövőbeni forgatásokat mutatjuk (a régebbieket nem -
  // azokhoz úgysincs már értelme diszpót küldeni), a "Forgatás dátuma" (kezdő
  // dátum) szerint csoportosítva: Tegnapi/Mai/Holnapi fix csoportok, utána a
  // további jövőbeni dátumok időrendben, mindegyik saját csoportként.
  const { upcoming, groups } = useMemo(() => {
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const tomorrow = new Date(now);
    tomorrow.setDate(now.getDate() + 1);
    const todayStr = localISODate(now);
    const yesterdayStr = localISODate(yesterday);
    const tomorrowStr = localISODate(tomorrow);

    const upcoming = filtered.filter((p) => (p.forgatas_datuma ?? "").slice(0, 10) >= yesterdayStr);

    const buckets = new Map<string, Project[]>();
    for (const p of upcoming) {
      const d = (p.forgatas_datuma ?? "").slice(0, 10);
      const key = d === yesterdayStr ? "Tegnapi" : d === todayStr ? "Mai" : d === tomorrowStr ? "Holnapi" : d;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key)!.push(p);
    }
    const fixedOrder = ["Tegnapi", "Mai", "Holnapi"];
    const restKeys = [...buckets.keys()].filter((k) => !fixedOrder.includes(k)).sort();
    const groups = [...fixedOrder, ...restKeys]
      .filter((k) => buckets.has(k))
      .map((key) => ({
        key,
        label: fixedOrder.includes(key) ? key : formatGroupDateLabel(key),
        projects: buckets.get(key)!.sort((a, b) => (a.forgatas_datuma ?? "").localeCompare(b.forgatas_datuma ?? "")),
      }));

    return { upcoming, groups };
  }, [filtered]);

  const elozetesKuldve = upcoming.filter((p) => p.elozetes_diszpo_kuldes).length;
  const teljesKuldve = upcoming.filter((p) => p.diszpo).length;

  return (
    <Card title={`Naptár / Diszpó (${upcoming.length} forgatás)`}>
      <p className="mb-3 text-[13px] text-text-secondary">
        {elozetesKuldve} előzetes diszpó elküldve · {teljesKuldve} teljes diszpó kiküldve · {upcoming.length - teljesKuldve} még hátra van
      </p>

      <div className="mb-3 flex flex-wrap items-center gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Szűrés bármelyik oszlopra…"
          className="w-full max-w-xs rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none"
        />
        <div className="flex items-center gap-1 rounded-[var(--radius)] border border-border p-0.5">
          <button
            type="button"
            onClick={() => setView("table")}
            className={`rounded-[calc(var(--radius)-2px)] px-2.5 py-1 text-[12px] ${
              view === "table" ? "bg-bg-accent text-text-accent" : "text-text-secondary hover:bg-surface-3"
            }`}
          >
            Táblázat
          </button>
          <button
            type="button"
            onClick={() => setView("calendar")}
            className={`rounded-[calc(var(--radius)-2px)] px-2.5 py-1 text-[12px] ${
              view === "calendar" ? "bg-bg-accent text-text-accent" : "text-text-secondary hover:bg-surface-3"
            }`}
          >
            Naptár
          </button>
        </div>
      </div>

      {view === "table" ? (
        groups.length === 0 ? (
          <p className="text-[13px] text-text-muted">
            {query ? "Nincs találat a szűrésre." : "Nincs tegnapi vagy jövőbeni forgatás."}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border">
                  <th className="whitespace-nowrap py-1.5 text-left font-medium text-text-secondary">Név</th>
                  <th className="whitespace-nowrap py-1.5 text-left font-medium text-text-secondary">Projektkód</th>
                  <th className="whitespace-nowrap py-1.5 text-left font-medium text-text-secondary">Forgatás dátuma</th>
                  <th className="whitespace-nowrap py-1.5 text-left font-medium text-text-secondary">Helyszín</th>
                  <th className="whitespace-nowrap py-1.5 text-left font-medium text-text-secondary">Előzetes diszpó</th>
                  <th className="whitespace-nowrap py-1.5 text-left font-medium text-text-secondary">Diszpó</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => (
                  <Fragment key={group.key}>
                    <tr>
                      <td colSpan={6} className="bg-surface-3/60 px-2 py-1.5 text-[12px] font-medium capitalize text-text-secondary">
                        {group.label} <span className="font-normal text-text-muted">({group.projects.length})</span>
                      </td>
                    </tr>
                    {group.projects.map((p) => (
                      <RowLink key={p.id} onClick={() => setModalProjectId(p.id)}>
                        <td className="py-2 pr-4">{p.nev}</td>
                        <td className="py-2 pr-4">{projectCodeById.get(p.project_code_id) ?? "–"}</td>
                        <td className="py-2 pr-4">
                          {p.forgatas_datuma_vege && p.forgatas_datuma_vege !== p.forgatas_datuma
                            ? `${formatDate(p.forgatas_datuma)} – ${formatDate(p.forgatas_datuma_vege)}`
                            : formatDate(p.forgatas_datuma)}
                        </td>
                        <td className="py-2 pr-4">{p.helyszin ?? "–"}</td>
                        <td className="py-2 pr-4">
                          <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                            {p.elozetes_diszpo_kuldes ? (
                              <StatusBadge label={p.elozetes_diszpo_kuldes} tone="teal" />
                            ) : (
                              <StatusBadge label="Nincs elküldve" tone="neutral" />
                            )}
                            {canSend && (
                              <ActionButton
                                path={`/api/v1/projects/${p.id}/diszpo/elozetes`}
                                label="Küldés"
                                confirmMessage="Elküldi az előzetes diszpót a résztvevőknek. Folytatod?"
                              />
                            )}
                          </div>
                        </td>
                        <td className="py-2 pr-4">
                          <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                            {p.diszpo ? (
                              <StatusBadge label={p.diszpo} tone="success" />
                            ) : (
                              <StatusBadge label="Nincs kiküldve" tone="neutral" />
                            )}
                            {canSend && (
                              <ActionButton
                                path={`/api/v1/projects/${p.id}/diszpo/kuldes`}
                                label="Küldés"
                                confirmMessage="Elküldi a teljes diszpót (technika listával, PDF-fel) a résztvevőknek. Folytatod?"
                              />
                            )}
                          </div>
                        </td>
                      </RowLink>
                    ))}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : (
        <ForgatasokCalendar projects={upcoming} onProjectClick={(id) => setModalProjectId(id)} />
      )}

      <ProjectDetailModal projectId={modalProjectId} projectCodes={projectCodes} onClose={() => setModalProjectId(null)} />
    </Card>
  );
}
