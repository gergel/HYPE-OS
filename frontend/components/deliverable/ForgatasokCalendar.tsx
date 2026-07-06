"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type CalendarProject = { id: number; nev: string; forgatas_datuma: string | null };

const WEEKDAY_LABELS = ["H", "K", "Sze", "Cs", "P", "Szo", "V"];
const MONTH_LABELS = [
  "január", "február", "március", "április", "május", "június",
  "július", "augusztus", "szeptember", "október", "november", "december",
];

function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
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

/** Havi nézetű naptár a forgatásokról (Project.forgatas_datuma) - innen
 * nyithatók meg az adott napi forgatások, és innen adható hozzájuk új
 * utómunka is, hogy a vágóknak ne kelljen a Projektek listát böngészniük. */
export function ForgatasokCalendar({ projects }: { projects: CalendarProject[] }) {
  const [monthCursor, setMonthCursor] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });

  const byDay = new Map<string, CalendarProject[]>();
  for (const p of projects) {
    if (!p.forgatas_datuma) continue;
    const key = p.forgatas_datuma.slice(0, 10);
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key)!.push(p);
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
      <div className="grid grid-cols-7 gap-px overflow-hidden rounded-[var(--radius)] border border-border bg-border text-[12px]">
        {WEEKDAY_LABELS.map((w) => (
          <div key={w} className="bg-surface-3 px-1.5 py-1 text-center text-text-muted">
            {w}
          </div>
        ))}
        {weeks.flatMap((week, wi) =>
          week.map((day, di) => {
            const key = toDateKey(day);
            const inMonth = day.getMonth() === monthCursor.getMonth();
            const dayProjects = byDay.get(key) ?? [];
            return (
              <div
                key={`${wi}-${di}`}
                className={`min-h-[5rem] bg-surface-2 p-1 ${inMonth ? "" : "opacity-40"} ${
                  key === todayKey ? "ring-1 ring-inset ring-[var(--color-text-accent)]" : ""
                }`}
              >
                <p className="mb-1 text-text-muted">{day.getDate()}</p>
                <div className="flex flex-col gap-0.5">
                  {dayProjects.map((p) => (
                    <div key={p.id} className="flex items-center gap-1 rounded bg-surface-3 px-1 py-0.5">
                      <a
                        href={`/projektek/${p.id}`}
                        className="min-w-0 flex-1 truncate text-text-secondary hover:text-text-accent hover:underline"
                        title={p.nev}
                      >
                        {p.nev}
                      </a>
                      <AddUtomunkaButton projectId={p.id} />
                    </div>
                  ))}
                </div>
              </div>
            );
          }),
        )}
      </div>
    </div>
  );
}
