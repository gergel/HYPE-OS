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

/** Csoport-fejléc színezése aszerint, hogy MIKOR KELL(ETT VOLNA) MEGÍRNI a
 * diszpót - nem aszerint, mikor van a forgatás.
 *
 * A diszpó egy nappal a forgatás előtt készül: ma a HOLNAPI napot írjuk. A mai
 * forgatás diszpója tehát tegnap ment ki, ma már nincs rajta teendő - ezért a
 * kiemelés (lila) a holnapi napé, "Ma írandó" címmel. Ami elmaradt (tegnapi és
 * mai forgatás diszpó nélkül), az narancs: az a lemaradás.
 *
 * A bal oldali sávot box-shadow rajzolja, nem border: a globals.css réteg
 * nélküli `* { border-color: ... }` szabálya felülírná a Tailwind
 * border-szín osztályait. */
const GROUP_TONES = {
  lemaradas: { bg: "bg-bg-orange", title: "text-text-orange", stripe: "shadow-[inset_4px_0_0_0_var(--text-orange)]" },
  mult: { bg: "bg-surface-3", title: "text-text-secondary", stripe: "shadow-[inset_4px_0_0_0_var(--border)]" },
  mairando: { bg: "bg-bg-accent", title: "text-text-accent", stripe: "shadow-[inset_4px_0_0_0_var(--accent-solid)]" },
  holnapirando: { bg: "bg-bg-blue", title: "text-text-blue", stripe: "shadow-[inset_4px_0_0_0_var(--text-blue)]" },
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

  /** Ha egy forgatásból leválasztottunk egy napot (feldarabolás), akkor arra a
   * napra MÁR A LEVÁLASZTOTT NAP a diszponálandó, nem az "egész".
   *
   * Az eredeti esemény korábban ilyenkor egyszerűen ELTŰNT a listáról. Ez
   * félrevezető volt: aki kereste, azt hitte, elveszett a forgatás. Most itt
   * marad, de kiírjuk rá, hogy fel van darabolva, és nem kérünk rá diszpót -
   * a küldés gombjai helyett egy jelölés van rajta, és egyik számlálóba sem
   * számít bele. */
  const { scheduled, darabolvaIdk, gyerekSzam } = useMemo(() => {
    const datumos = projects.filter((p) => p.forgatas_datuma !== null);
    const napraDarabolt = new Set(
      datumos
        .filter((p) => p.feldarabolas_szulo_id !== null)
        .map((p) => `${p.feldarabolas_szulo_id}|${(p.forgatas_datuma ?? "").slice(0, 10)}`),
    );
    // HÁNY napot választottunk le róla - ezt a szülőn akkor is kiírjuk, ha még
    // maradt saját napja (a darabolás kivágja a leválasztott napot az
    // eredetiből, tehát a szülő gyakran egy MÁSIK napon áll a listán). Enélkül
    // ott csak egy megrövidült forgatás látszik, magyarázat nélkül.
    const gyerekSzam = new Map<number, number>();
    for (const p of projects) {
      if (p.feldarabolas_szulo_id === null) continue;
      gyerekSzam.set(p.feldarabolas_szulo_id, (gyerekSzam.get(p.feldarabolas_szulo_id) ?? 0) + 1);
    }
    return {
      scheduled: datumos,
      gyerekSzam,
      darabolvaIdk: new Set(
        datumos
          .filter((p) => napraDarabolt.has(`${p.id}|${(p.forgatas_datuma ?? "").slice(0, 10)}`))
          .map((p) => p.id),
      ),
    };
  }, [projects]);

  /** Amin nincs diszpó-teendő: a meetingek és a felaprított eredeti események. */
  const nincsRajtaTeendo = (p: Project) => p.nem_diszponalando || darabolvaIdk.has(p.id);

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
    const nap = (eltolas: number) => {
      const d = new Date(now);
      d.setDate(now.getDate() + eltolas);
      return localISODate(d);
    };
    const yesterdayStr = nap(-1);
    const todayStr = nap(0);
    const tomorrowStr = nap(1);
    // Amit ma írunk, az a HOLNAPI forgatás; a holnaputánit holnap.
    const holnaputanStr = nap(2);

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
        const items = buckets.get(iso)!;
        const hatra = items.filter((p) => !p.diszpo && !nincsRajtaTeendo(p)).length;
        // A csoportot az alapján soroljuk be, hogy MIKOR KELL MEGÍRNI a
        // diszpót - a forgatás előtti napon. A mai és a tegnapi forgatás
        // diszpója tehát már elmúlt feladat: csak akkor kiabál (narancs), ha
        // tényleg maradt rajta hátra, egyébként semleges.
        const tone: GroupTone =
          iso === tomorrowStr
            ? "mairando"
            : iso === holnaputanStr
              ? "holnapirando"
              : iso <= todayStr
                ? hatra > 0
                  ? "lemaradas"
                  : "mult"
                : "future";
        const napNeve = capitalize(parseISODate(iso).toLocaleDateString("hu-HU", { weekday: "long" }));
        const title =
          iso === tomorrowStr
            ? "Ma írandó"
            : iso === holnaputanStr
              ? "Holnap írandó"
              : iso === todayStr
                ? "Mai forgatás"
                : iso === yesterdayStr
                  ? "Tegnapi forgatás"
                  : napNeve;
        return {
          key: iso,
          tone,
          title,
          // A cím a TEENDŐ napját mondja meg ("Ma írandó"), a dátum viszont a
          // forgatásé - ezért az "Ma írandó" mellé kiírjuk, melyik napról szól.
          alcim: iso === tomorrowStr || iso === holnaputanStr ? `${napNeve}i forgatás` : null,
          dateLabel: parseISODate(iso).toLocaleDateString("hu-HU", { year: "numeric", month: "long", day: "numeric" }),
          projects: items,
          pending: hatra,
          meetings: items.filter((p) => p.nem_diszponalando).length,
          darabolt: items.filter((p) => darabolvaIdk.has(p.id) && !p.nem_diszponalando).length,
        };
      });

    return { upcoming, groups };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtered, darabolvaIdk]);

  // A meetingek/helyszínbejárások (a naptárban lila események) benne maradnak a
  // listában - a naptár úgy teljes, ahogy van -, de EGYIK diszpó-számlálóba sem
  // számítanak bele: nincs rajtuk elvégzendő teendő.
  const diszponalando = upcoming.filter((p) => !nincsRajtaTeendo(p));
  const meetingek = upcoming.filter((p) => p.nem_diszponalando).length;
  const daraboltak = upcoming.filter((p) => darabolvaIdk.has(p.id) && !p.nem_diszponalando).length;
  const elozetesKuldve = diszponalando.filter((p) => p.elozetes_diszpo_kuldes).length;
  const teljesKuldve = diszponalando.filter((p) => p.diszpo).length;
  // A MAI TEENDŐ: a holnapi forgatások diszpója (és ami korábbról elmaradt) -
  // ez a szám az, amiért valaki ezt az oldalt megnyitja.
  const maIrando = groups.find((g) => g.tone === "mairando")?.pending ?? 0;
  const lemaradas = groups
    .filter((g) => g.tone === "lemaradas")
    .reduce((osszeg, g) => osszeg + g.pending, 0);

  return (
    <Card title={`Naptár / Diszpó (${diszponalando.length} forgatás)`}>
      {/* A diszpó egy nappal a forgatás előtt készül: ma a HOLNAPI napot írjuk.
          Ezért ez a szám áll elöl, nem az összes hátralévő. */}
      <p className="mb-1 text-[13px] text-text-primary">
        <strong>{maIrando} diszpó írandó ma</strong> (a holnapi forgatásokra)
        {lemaradas > 0 && (
          <span className="text-text-orange"> · {lemaradas} lemaradás (mai vagy tegnapi forgatás)</span>
        )}
      </p>
      <p className="mb-3 text-[13px] text-text-secondary">
        {elozetesKuldve} előzetes diszpó elküldve · {teljesKuldve} teljes diszpó kiküldve ·{" "}
        {diszponalando.length - teljesKuldve} még hátra van összesen
        {meetingek > 0 && ` · ${meetingek} meeting (nem diszponálandó)`}
        {daraboltak > 0 && ` · ${daraboltak} feldarabolva (a napjaihoz megy a diszpó)`}
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
                    {group.alcim && <span className="text-[12px] text-text-secondary">({group.alcim})</span>}
                    <span className="text-[12px] text-text-secondary">{group.dateLabel}</span>
                    <span className="ml-auto text-[12px] text-text-muted">
                      {group.projects.length - group.meetings - group.darabolt} forgatás
                      {group.meetings > 0 && ` · ${group.meetings} meeting`}
                      {group.darabolt > 0 && ` · ${group.darabolt} feldarabolva`}
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
                            {/* Ha leválasztottunk róla napokat, azt akkor is
                                kiírjuk, ha erre a napra még kell rá diszpó:
                                különben csak egy megrövidült forgatás látszik,
                                magyarázat nélkül. */}
                            {gyerekSzam.get(p.id)
                              ? ` · feldarabolva (${gyerekSzam.get(p.id)} nap leválasztva)`
                              : ""}
                            {p.feldarabolas_szulo_id !== null ? " · leválasztott nap" : ""}
                          </p>
                        </div>

                        {darabolvaIdk.has(p.id) && !p.nem_diszponalando ? (
                          // Ez az eredeti, több napos esemény, amiből erre a
                          // napra leválasztottunk egy külön forgatást: a diszpó
                          // ahhoz megy, ide nem kérünk semmit.
                          <div className="flex flex-wrap items-center gap-2">
                            <StatusBadge label="Már feldarabolva" tone="neutral" />
                            <span className="text-[12px] text-text-muted">
                              a diszpó a leválasztott naphoz megy, ide nem kell
                            </span>
                          </div>
                        ) : p.nem_diszponalando ? (
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
                                  label={p.elozetes_diszpo_kuldes ? "Újraküldés" : "Küldés"}
                                  figyelmeztetes={
                                    p.elozetes_diszpo_kuldes ? "AZ ELŐZETES DISZPÓ MÁR KI VAN KÜLDVE" : undefined
                                  }
                                  megerositoCimke={p.elozetes_diszpo_kuldes ? "Igen, újraküldöm" : undefined}
                                  confirmMessage={
                                    p.elozetes_diszpo_kuldes
                                      ? `${p.nev} – állapot: ${p.elozetes_diszpo_kuldes}. Ha most újraküldöd, a stáb MÉG EGYSZER megkapja ugyanazt a levelet. Biztosan újraküldöd?`
                                      : "Elküldi az előzetes diszpót a résztvevőknek. Folytatod?"
                                  }
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
                                  label={p.diszpo ? "Újraküldés" : "Küldés"}
                                  figyelmeztetes={p.diszpo ? "A DISZPÓ MÁR KI VAN KÜLDVE" : undefined}
                                  megerositoCimke={p.diszpo ? "Igen, újraküldöm" : undefined}
                                  confirmMessage={
                                    p.diszpo
                                      ? `${p.nev} – állapot: ${p.diszpo}. Ha most újraküldöd, a stáb MÉG EGYSZER megkapja a teljes diszpót (technika listával, PDF-fel). Biztosan újraküldöd?`
                                      : "Elküldi a teljes diszpót (technika listával, PDF-fel) a résztvevőknek. Folytatod?"
                                  }
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
        // A naptárban a felaprított eredeti esemény NEM jelenik meg: ott a nap
        // egy csempe, és a leválasztott nap mellett az "egész" csak ugyanannak
        // a forgatásnak a duplikátuma lenne. A listán viszont ott marad,
        // jelöléssel - lásd darabolvaIdk.
        <ForgatasokCalendar
          projects={upcoming.filter((p) => !darabolvaIdk.has(p.id))}
          onProjectClick={(id) => setModalProjectId(id)}
        />
      )}

      <ProjectDetailModal projectId={modalProjectId} onClose={() => setModalProjectId(null)} />
    </Card>
  );
}
