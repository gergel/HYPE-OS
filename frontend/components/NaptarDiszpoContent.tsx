"use client";

import { useMemo, useState } from "react";
import { ActionButton } from "@/components/ActionButton";
import { Card } from "@/components/Card";
import { ForgatasokCalendar } from "@/components/deliverable/ForgatasokCalendar";
import { ProjectDetailModal } from "@/components/ProjectDetailModal";
import { StatusBadge } from "@/components/StatusBadge";
import type { Project, ProjectCode } from "@/lib/api";

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : "–";
}

/** YYYY-MM-DD, helyi időzóna szerint (nem UTC - a Date#toISOString() a
 * böngésző UTC-eltolása miatt éjfél körül átcsúsztatná a "ma" dátumát). */
function localISODate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function parseISODate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** Csoport-fejléc színezése: a tegnapi (lemaradásban) narancs, a mai lila
 * (kiemelt), a holnapi kék, a távolabbiak semlegesek - hogy ránézésre látszódjon,
 * melyik nap sürgős. A bal oldali sávot box-shadow rajzolja, nem border: a
 * globals.css réteg nélküli `* { border-color: ... }` szabálya felülírná a
 * Tailwind border-szín osztályait. */
const GROUP_TONES = {
  past: { bg: "bg-bg-orange", title: "text-text-orange", stripe: "shadow-[inset_4px_0_0_0_var(--text-orange)]" },
  today: { bg: "bg-bg-accent", title: "text-text-accent", stripe: "shadow-[inset_4px_0_0_0_var(--accent-solid)]" },
  tomorrow: { bg: "bg-bg-blue", title: "text-text-blue", stripe: "shadow-[inset_4px_0_0_0_var(--text-blue)]" },
  future: { bg: "bg-surface-3", title: "text-text-primary", stripe: "shadow-[inset_4px_0_0_0_var(--border)]" },
} as const;

type GroupTone = keyof typeof GROUP_TONES;

/** A Naptár/Diszpó oldal tényleges tartalma - a Project rekordokon
 * ténylegesen tárolt diszpó-állapotot (diszpo/elozetes_diszpo_kuldes,
 * lásd backend/app/services/dispo.py) mutatja meg, a két meglévő küldés-
 * végpontra (POST .../diszpo/elozetes, .../diszpo/kuldes) mutató gombokkal -
 * ugyanazok az akciók, amik eddig csak a Projekt részletnézet "Diszpó küldése"
 * fülén voltak elérhetők, itt viszont egy helyen, az összes közelgő forgatásra
 * rálátva.
 *
 * A lista NEM egy sűrű táblázat, hanem naponként külön dobozokra bontva jelenik
 * meg (Tegnapi/Mai/Holnapi, majd dátumonként) - a diszpó-küldés napi ritmusú
 * feladat, így ránézésre látszik, melyik napon mi van még hátra. */
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

  const scheduled = useMemo(() => {
    const datumos = projects.filter((p) => p.forgatas_datuma !== null);
    // Ha egy forgatásból leválasztottunk egy napot (feldarabolás), akkor arra a
    // napra MÁR A LEVÁLASZTOTT NAP a diszponálandó - az "egész" nem jön fel
    // még egyszer. Enélkül ugyanaz a nap kétszer szerepelne: az eredeti
    // projektként és a leválasztott napként is.
    const napraDarabolt = new Set(
      datumos
        .filter((p) => p.feldarabolas_szulo_id !== null)
        .map((p) => `${p.feldarabolas_szulo_id}|${(p.forgatas_datuma ?? "").slice(0, 10)}`),
    );
    return datumos.filter((p) => !napraDarabolt.has(`${p.id}|${(p.forgatas_datuma ?? "").slice(0, 10)}`));
  }, [projects]);

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

  // Csak a tegnapi és a jövőbeni forgatások kerülnek a listába (a régebbiekhez
  // már nincs értelme diszpót küldeni), a forgatás kezdő dátuma szerint
  // csoportosítva. A kulcs mindig maga a dátum, így a sima növekvő rendezés
  // adja a helyes sorrendet: tegnap, ma, holnap, majd a további napok.
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
      const key = (p.forgatas_datuma ?? "").slice(0, 10);
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key)!.push(p);
    }

    const groups = [...buckets.keys()]
      .sort()
      .map((iso) => {
        const tone: GroupTone =
          iso === yesterdayStr ? "past" : iso === todayStr ? "today" : iso === tomorrowStr ? "tomorrow" : "future";
        const title =
          tone === "past"
            ? "Tegnapi"
            : tone === "today"
              ? "Mai"
              : tone === "tomorrow"
                ? "Holnapi"
                : capitalize(parseISODate(iso).toLocaleDateString("hu-HU", { weekday: "long" }));
        const items = buckets.get(iso)!;
        return {
          key: iso,
          tone,
          title,
          dateLabel: parseISODate(iso).toLocaleDateString("hu-HU", { year: "numeric", month: "long", day: "numeric" }),
          projects: items,
          pending: items.filter((p) => !p.diszpo && !p.nem_diszponalando).length,
          meetings: items.filter((p) => p.nem_diszponalando).length,
        };
      });

    return { upcoming, groups };
  }, [filtered]);

  // A meetingek/helyszínbejárások (a naptárban lila események) benne maradnak a
  // listában - a naptár úgy teljes, ahogy van -, de EGYIK diszpó-számlálóba sem
  // számítanak bele: nincs rajtuk elvégzendő teendő.
  const diszponalando = upcoming.filter((p) => !p.nem_diszponalando);
  const meetingek = upcoming.length - diszponalando.length;
  const elozetesKuldve = diszponalando.filter((p) => p.elozetes_diszpo_kuldes).length;
  const teljesKuldve = diszponalando.filter((p) => p.diszpo).length;

  return (
    <Card title={`Naptár / Diszpó (${diszponalando.length} forgatás)`}>
      <p className="mb-3 text-[13px] text-text-secondary">
        {elozetesKuldve} előzetes diszpó elküldve · {teljesKuldve} teljes diszpó kiküldve ·{" "}
        {diszponalando.length - teljesKuldve} még hátra van
        {meetingek > 0 && ` · ${meetingek} meeting (nem diszponálandó)`}
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Szűrés bármelyik adatra…"
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
            Lista
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
          <div className="space-y-5">
            {groups.map((group) => {
              const tone = GROUP_TONES[group.tone];
              return (
                <section key={group.key} className="overflow-hidden rounded-[var(--radius-lg)] border border-border">
                  <div className={`flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-3 ${tone.bg} ${tone.stripe}`}>
                    <span className={`text-[15px] font-semibold ${tone.title}`}>{group.title}</span>
                    <span className="text-[12px] text-text-secondary">{group.dateLabel}</span>
                    <span className="ml-auto text-[12px] text-text-muted">
                      {group.projects.length - group.meetings} forgatás
                      {group.meetings > 0 && ` · ${group.meetings} meeting`}
                      {group.pending > 0 && ` · ${group.pending} diszpó hátra`}
                    </span>
                  </div>

                  <div className="divide-y divide-border">
                    {group.projects.map((p) => (
                      <div
                        key={p.id}
                        onClick={() => setModalProjectId(p.id)}
                        className="flex cursor-pointer flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 transition-colors hover:bg-surface-3"
                      >
                        <div className="min-w-[200px] flex-1">
                          <p className="text-[14px] font-medium text-text-primary">{p.nev}</p>
                          <p className="mt-0.5 text-[12px] text-text-muted">
                            {projectCodeById.get(p.project_code_id) ?? "–"}
                            {p.helyszin ? ` · ${p.helyszin}` : ""}
                            {p.forgatas_datuma_vege && p.forgatas_datuma_vege !== p.forgatas_datuma
                              ? ` · ${formatDate(p.forgatas_datuma)} – ${formatDate(p.forgatas_datuma_vege)}`
                              : ""}
                          </p>
                        </div>

                        {p.nem_diszponalando ? (
                          <div className="flex flex-wrap items-center gap-2">
                            <StatusBadge label="Meeting – nem diszponálandó" tone="neutral" />
                            {p.naptar_szin && (
                              <span className="text-[12px] text-text-muted">naptár szín: {p.naptar_szin}</span>
                            )}
                          </div>
                        ) : (
                        <div
                          className="flex flex-wrap items-end gap-x-6 gap-y-3"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <div>
                            <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                              Előzetes diszpó
                            </p>
                            <div className="flex items-center gap-2">
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
                          </div>

                          <div>
                            <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                              Diszpó
                            </p>
                            <div className="flex items-center gap-2">
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
                          </div>
                        </div>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        )
      ) : (
        <ForgatasokCalendar projects={upcoming} onProjectClick={(id) => setModalProjectId(id)} />
      )}

      <ProjectDetailModal projectId={modalProjectId} onClose={() => setModalProjectId(null)} />
    </Card>
  );
}
