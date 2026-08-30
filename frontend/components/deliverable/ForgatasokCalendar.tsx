"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { StatusBadge } from "@/components/StatusBadge";

type CalendarProject = {
  id: number;
  nev: string;
  forgatas_datuma: string | null;
  forgatas_datuma_vege: string | null;
  /** "08:30:00" alakban, ha meg van adva - a naptárból is átjön. */
  forgatas_kezdes_ido?: string | null;
  /** Csak akkor van értéke, ha a hívó valódi Project-et ad át (mind a négy
   * hívó oldal ezt teszi, lásd ForgatasokCalendar docstring) - a több napos
   * sáv ezzel mutatja a diszpó-állapotot, mint egy kártyán. */
  diszpo?: string | null;
};

/** A kezdés órája a naptár-bejegyzés elé ("08:30 Projekt neve") - csak ha a
 * felhasználó (vagy a naptár-szinkron) meg is adta. */
function startTimeLabel(p: CalendarProject): string {
  return p.forgatas_kezdes_ido ? p.forgatas_kezdes_ido.slice(0, 5) : "";
}

const WEEKDAY_LABELS = ["H", "K", "Sze", "Cs", "P", "Szo", "V"];
const MONTH_LABELS = [
  "január", "február", "március", "április", "május", "június",
  "július", "augusztus", "szeptember", "október", "november", "december",
];

// Elég magas két sornak (cím + diszpó-állapot pill), hogy a több napos sáv
// jól látható KÁRTYAKÉNT fusson át az érintett napokon - nem egy alig
// észrevehető vékony csíkként, mint korábban.
const BAR_LANE_HEIGHT = 40;
// A napi cella tetején lévő "p-1" padding (4px) + a dátumszám sor magassága
// (lásd lejjebb a dátumszám elem explicit height/lineHeight stílusa) - erre
// van szükség, hogy a több napos sáv pontosan a dátumszám ALÁ kerüljön (ne
// föléje), ugyanoda, ahol az egynapos események pillái is kezdődnek.
const CELL_PADDING = 4;
const DATE_ROW_HEIGHT = 18;
const BARS_TOP_OFFSET = CELL_PADDING + DATE_ROW_HEIGHT;

function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function parseDateOnly(value: string): Date {
  const [y, m, d] = value.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

function diffDays(a: Date, b: Date): number {
  return Math.round((a.getTime() - b.getTime()) / 86_400_000);
}

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

/** Naptár-rácsot épít a hónaphoz - a hónap első hetének hétfőjétől az utolsó
 * hetének vasárnapjáig, hogy a szomszédos hónapok napjai is látszódjanak a
 * szélükön (mint egy szokásos hónap-nézet), de ne legyen felesleges, teljesen
 * üres hatodik sor, ha nem szükséges. */
function buildWeeks(monthCursor: Date): Date[][] {
  const firstOfMonth = new Date(monthCursor.getFullYear(), monthCursor.getMonth(), 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7;
  const start = new Date(firstOfMonth);
  start.setDate(start.getDate() - startOffset);

  const lastOfMonth = new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 0);
  const endOffset = (7 - ((lastOfMonth.getDay() + 6) % 7) - 1) % 7;
  const end = new Date(lastOfMonth);
  end.setDate(end.getDate() + endOffset);

  const weeks: Date[][] = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    const week: Date[] = [];
    for (let i = 0; i < 7; i++) {
      week.push(new Date(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(week);
  }
  return weeks;
}

type MultiDayBar = {
  /** A reprezentáns elem (a legkorábban kezdődő) - erre mutat a kattintás/link. */
  project: CalendarProject;
  start: Date;
  end: Date;
  /** Csak akkor van értéke, ha az ÖSSZES összevont elem UGYANAZT a diszpó-
   * állapotot hordozza - eltérő állapotoknál (pl. az egyik nap már kiküldve,
   * a másik még nem) félrevezető lenne egyetlen pillt mutatni, ezért ilyenkor
   * nincs pill, csak a cím. */
  diszpo: string | null | undefined;
};
type PlacedBar = MultiDayBar & { startCol: number; endCol: number; lane: number };

type NevesIdoszak = { project: CalendarProject; start: Date; end: Date };
type OsszevontIdoszak = NevesIdoszak & { diszpo: string | null | undefined };

function combinedDiszpo(items: CalendarProject[]): string | null | undefined {
  const first = items[0];
  if (first.diszpo === undefined) return undefined;
  return items.every((p) => p.diszpo === first.diszpo) ? first.diszpo : undefined;
}

/** A HYPE OS-es projekt-adatok gyakran NEM egyetlen rekordban hordozzák a
 * több napos forgatás teljes tartományát: a Notionből (vagy a diszpó saját
 * "feldarabolás" funkciójából, lásd NaptarDiszpoContent) sokszor NAPONKÉNT
 * külön Project sor jön át, azonos névvel. Emiatt a puszta forgatas_datuma/
 * forgatas_datuma_vege alapján épített sáv-logika (lásd MultiDayBar fent)
 * önmagában nem elég: itt ÖSSZEVONJUK az azonos nevű, EGYMÁST ÉRŐ vagy
 * átfedő napú elemeket egyetlen időszakká, mielőtt sávvá alakítanánk őket -
 * így egy 3 külön sorból álló, 3 napos forgatás is EGY, átívelő kártyaként
 * jelenik meg, nem 3 külön napi pill-ként. Egy valódi, egy rekordban tárolt
 * több napos forgatás (forgatas_datuma_vege kitöltve) ugyanezen az úton megy
 * át, változatlan eredménnyel (nincs mivel összevonni). */
function osszevonNaponkentiSorokat(items: NevesIdoszak[]): OsszevontIdoszak[] {
  const byName = new Map<string, NevesIdoszak[]>();
  for (const it of items) {
    if (!byName.has(it.project.nev)) byName.set(it.project.nev, []);
    byName.get(it.project.nev)!.push(it);
  }

  const result: OsszevontIdoszak[] = [];
  for (const list of byName.values()) {
    list.sort((a, b) => a.start.getTime() - b.start.getTime());
    let group: NevesIdoszak[] = [];
    let groupEnd: Date | null = null;
    const flush = () => {
      if (group.length === 0) return;
      const start = group[0].start;
      const end = group.reduce((max, it) => (it.end > max ? it.end : max), group[0].end);
      result.push({ project: group[0].project, start, end, diszpo: combinedDiszpo(group.map((it) => it.project)) });
      group = [];
      groupEnd = null;
    };
    for (const it of list) {
      if (group.length > 0 && groupEnd !== null && diffDays(it.start, groupEnd) > 1) {
        flush();
      }
      group.push(it);
      groupEnd = groupEnd === null || it.end.getTime() > groupEnd.getTime() ? it.end : groupEnd;
    }
    flush();
  }
  return result;
}

/** Egy héten belül a több napos forgatásokhoz "sáv" (lane) indexet rendel,
 * hogy az egymást átfedő sávok ne csússzanak egymásra - mohó algoritmus: a
 * legkorábban kezdődő sáv kapja az első szabad sort, amelyben az előző sáv
 * már véget ért. Ugyanaz a minta, mint a szokásos "több napos esemény"
 * naptár-nézeteknél (pl. Google/Notion naptár). */
function placeBarsForWeek(bars: MultiDayBar[], weekStart: Date, weekEnd: Date): PlacedBar[] {
  const inWeek = bars
    .filter((b) => b.start <= weekEnd && b.end >= weekStart)
    .map((b) => ({
      ...b,
      startCol: clamp(diffDays(b.start, weekStart), 0, 6),
      endCol: clamp(diffDays(b.end, weekStart), 0, 6),
    }))
    .sort((a, b) => a.startCol - b.startCol || b.endCol - b.startCol - (a.endCol - a.startCol));

  const laneEnds: number[] = [];
  return inWeek.map((b) => {
    let lane = laneEnds.findIndex((endCol) => endCol < b.startCol);
    if (lane === -1) {
      lane = laneEnds.length;
      laneEnds.push(b.endCol);
    } else {
      laneEnds[lane] = b.endCol;
    }
    return { ...b, lane };
  });
}

/** Egy adott forgatáshoz (Project) új utómunkát hoz létre - ugyanaz a backend
 * akció, mint a Projekt oldal "+ Utómunka létrehozása" gombja, csak innen, a
 * naptárból is elérhető, hogy a vágónak ne kelljen külön megkeresnie a
 * projektet. */
function AddUtomunkaButton({ projectId }: { projectId: number }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function create() {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/projects/${projectId}/create-utomunka`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      const data = await res.json();
      router.push(`/utomunka/${data.id}`);
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={create}
      disabled={busy}
      title="Új utómunka létrehozása ehhez a forgatáshoz"
      className="shrink-0 rounded px-1 text-[12px] leading-none text-text-accent hover:bg-surface-2 disabled:opacity-50"
    >
      +
    </button>
  );
}

/** Havi nézetű naptár a forgatásokról (Project.forgatas_datuma /
 * forgatas_datuma_vege) - innen nyithatók meg az adott napi forgatások, és
 * innen adható hozzájuk új utómunka is, hogy a vágóknak ne kelljen a
 * Projektek listát böngészniük. A több napos forgatások egy, a teljes
 * időtartamukon átívelő sávként jelennek meg minden érintett hét tetején -
 * NEM ismétlődnek külön-külön minden napi cellában -, az egynapos forgatások
 * pedig változatlanul a saját napjuk cellájában, kis "pill"-ként. A sáv jól
 * látható KÁRTYA (cím + diszpó-állapot pill, ha az összevont napok azonos
 * állapotúak), nem csak egy vékony csík.
 *
 * A "több napos" nemcsak azt jelenti, hogy EGY Project rekordon van kitöltve
 * a forgatas_datuma_vege - a valódi adatban egy több napos forgatás gyakran
 * NAPONKÉNT külön Project sorként jön át (Notion-import vagy a diszpó saját
 * "feldarabolás" funkciója miatt, lásd NaptarDiszpoContent), azonos névvel.
 * Ezért az azonos nevű, egymást érő/átfedő napú sorokat ÖSSZEVONJUK, mielőtt
 * sávvá alakítanánk (lásd osszevonNaponkentiSorokat) - a mögöttes rekordok
 * külön maradnak (saját diszpó-állapot, saját szerkeszthetőség), csak a
 * MEGJELENÍTÉS füzi össze őket egyetlen kártyává. */
export function ForgatasokCalendar({
  projects,
  onProjectClick,
}: {
  projects: CalendarProject[];
  /** Ha meg van adva, egy projektre kattintás ezt hívja meg (a projekt id-
   * jével) a `/projektek/{id}`-re navigálás HELYETT - pl. felugró ablakban
   * való megnyitáshoz (lásd ProjektekContent.tsx). Az Utómunka oldal nem ad
   * meg ilyet, ott változatlanul a teljes oldalra navigál kattintás. */
  onProjectClick?: (id: number) => void;
}) {
  const [monthCursor, setMonthCursor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const rawIdoszakok: NevesIdoszak[] = [];
  for (const p of projects) {
    if (!p.forgatas_datuma) continue;
    const start = parseDateOnly(p.forgatas_datuma);
    const end = p.forgatas_datuma_vege ? parseDateOnly(p.forgatas_datuma_vege) : start;
    rawIdoszakok.push({ project: p, start, end: end.getTime() > start.getTime() ? end : start });
  }

  const multiDayBars: MultiDayBar[] = [];
  const byDay = new Map<string, CalendarProject[]>();
  for (const it of osszevonNaponkentiSorokat(rawIdoszakok)) {
    if (it.end.getTime() > it.start.getTime()) {
      multiDayBars.push({ project: it.project, start: it.start, end: it.end, diszpo: it.diszpo });
      continue;
    }
    const key = toDateKey(it.start);
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key)!.push(it.project);
  }

  const weeks = buildWeeks(monthCursor);
  const todayKey = toDateKey(new Date());

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setMonthCursor(new Date(monthCursor.getFullYear(), monthCursor.getMonth() - 1, 1))}
          className="rounded border border-border px-2 py-1 text-[13px] text-text-secondary hover:bg-surface-3"
        >
          ‹
        </button>
        <p className="text-[13px] font-medium text-text-primary">
          {MONTH_LABELS[monthCursor.getMonth()]} {monthCursor.getFullYear()}
        </p>
        <button
          type="button"
          onClick={() => setMonthCursor(new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 1))}
          className="rounded border border-border px-2 py-1 text-[13px] text-text-secondary hover:bg-surface-3"
        >
          ›
        </button>
      </div>
      <div className="overflow-hidden rounded-[var(--radius)] border border-border text-[12px]">
        <div className="grid grid-cols-7 gap-px bg-border">
          {WEEKDAY_LABELS.map((w) => (
            <div key={w} className="bg-surface-3 px-1.5 py-1 text-center text-text-muted">
              {w}
            </div>
          ))}
        </div>
        {weeks.map((week, wi) => {
          const weekStart = week[0];
          const weekEnd = week[6];
          const placedBars = placeBarsForWeek(multiDayBars, weekStart, weekEnd);
          const laneCount = placedBars.reduce((max, b) => Math.max(max, b.lane + 1), 0);
          return (
            <div key={wi} className="relative border-t border-border">
              <div className="grid grid-cols-7 gap-px bg-border">
                {week.map((day, di) => {
                  const key = toDateKey(day);
                  const inMonth = day.getMonth() === monthCursor.getMonth();
                  const dayProjects = byDay.get(key) ?? [];
                  return (
                    <div
                      key={di}
                      className={`min-h-[5rem] bg-surface-2 p-1 ${inMonth ? "" : "opacity-40"} ${
                        key === todayKey ? "ring-1 ring-inset ring-[var(--color-text-accent)]" : ""
                      }`}
                    >
                      <p className="text-text-muted" style={{ height: DATE_ROW_HEIGHT, lineHeight: `${DATE_ROW_HEIGHT}px` }}>
                        {day.getDate()}
                      </p>
                      {laneCount > 0 && <div style={{ height: laneCount * BAR_LANE_HEIGHT }} />}
                      <div className="flex flex-col gap-0.5">
                        {dayProjects.map((p) => (
                          <div key={p.id} className="flex items-center gap-1 rounded bg-surface-3 px-1 py-0.5">
                            <a
                              href={`/projektek/${p.id}`}
                              onClick={
                                onProjectClick
                                  ? (e) => {
                                      e.preventDefault();
                                      onProjectClick(p.id);
                                    }
                                  : undefined
                              }
                              className="min-w-0 flex-1 truncate text-text-secondary hover:text-text-accent hover:underline"
                              title={startTimeLabel(p) ? `${startTimeLabel(p)} – ${p.nev}` : p.nev}
                            >
                              {startTimeLabel(p) && <span className="mr-1 text-text-muted">{startTimeLabel(p)}</span>}
                              {p.nev}
                            </a>
                            <AddUtomunkaButton projectId={p.id} />
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
              {laneCount > 0 && (
                <div
                  className="pointer-events-none absolute right-0 left-0 px-px"
                  style={{ top: BARS_TOP_OFFSET, height: laneCount * BAR_LANE_HEIGHT }}
                >
                  {placedBars.map((b) => (
                    <a
                      key={b.project.id}
                      href={`/projektek/${b.project.id}`}
                      onClick={
                        onProjectClick
                          ? (e) => {
                              e.preventDefault();
                              onProjectClick(b.project.id);
                            }
                          : undefined
                      }
                      className="pointer-events-auto absolute flex flex-col justify-center gap-0.5 overflow-hidden rounded-[6px] border border-border bg-surface-3 px-1.5 py-0.5 leading-tight hover:border-text-accent"
                      style={{
                        left: `${(b.startCol / 7) * 100}%`,
                        width: `${((b.endCol - b.startCol + 1) / 7) * 100}%`,
                        top: b.lane * BAR_LANE_HEIGHT,
                        height: BAR_LANE_HEIGHT - 2,
                      }}
                      title={b.project.nev}
                    >
                      <span className="truncate text-[12px] font-medium text-text-primary">{b.project.nev}</span>
                      {/* A diszpó-állapot csak akkor van (lásd CalendarProject.diszpo),
                          ha a hívó valódi Project-et adott át (eddig mind a négy oldal ezt
                          teszi), ÉS az összevont napok mindegyike UGYANAZT az állapotot
                          hordozza (lásd combinedDiszpo) - eltérő állapotoknál nincs pill. */}
                      {b.diszpo !== undefined && (
                        <span className="truncate leading-none">
                          <StatusBadge label={b.diszpo ? b.diszpo : "Nincs kiküldve"} tone={b.diszpo ? "success" : "neutral"} />
                        </span>
                      )}
                    </a>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
