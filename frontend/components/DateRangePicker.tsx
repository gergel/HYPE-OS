"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export type DateRangeValue = {
  /** "YYYY-MM-DD" vagy üres */
  start: string;
  /** "HH:MM" vagy üres */
  startTime: string;
  end: string;
  endTime: string;
};

type DateFormat = "full" | "short" | "iso";

const FORMAT_LABELS: Record<DateFormat, string> = {
  full: "Teljes dátum",
  short: "Rövid",
  iso: "ÉÉÉÉ-HH-NN",
};

const FORMAT_STORAGE_KEY = "hype_os_date_format";
const WEEKDAYS = ["H", "K", "Sze", "Cs", "P", "Szo", "V"];
const MONTHS = [
  "január",
  "február",
  "március",
  "április",
  "május",
  "június",
  "július",
  "augusztus",
  "szeptember",
  "október",
  "november",
  "december",
];

function parseISO(value: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function toISO(date: Date): string {
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${m}-${d}`;
}

function formatDate(value: string, format: DateFormat): string {
  const date = parseISO(value);
  if (!date) return "";
  if (format === "iso") return value;
  if (format === "short") return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")}.`;
  return `${date.getFullYear()}. ${MONTHS[date.getMonth()]} ${date.getDate()}.`;
}

/** A hónap rácsa HÉTFŐVEL kezdve, az előző/következő hónap kilógó napjaival
 * feltöltve, hogy mindig teljes hetek legyenek (6 sor = fix magasság, nem
 * ugrál a felület hónapváltáskor). */
function monthGrid(cursor: Date): Date[] {
  const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7; // vasárnap=0 -> hétfő-alapú index
  const start = new Date(first);
  start.setDate(first.getDate() - offset);
  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    return d;
  });
}

/** Szerver-oldali rendereléskor nincs localStorage - ilyenkor az alapértelmezett
 * formátum jön, és a hidratálás után sem ugrik, mert a választó csak
 * kattintásra nyílik ki. */
function readStoredFormat(): DateFormat {
  if (typeof window === "undefined") return "full";
  const stored = window.localStorage.getItem(FORMAT_STORAGE_KEY);
  return stored === "short" || stored === "iso" || stored === "full" ? stored : "full";
}

/** "9" -> "09:00", "930" / "9:3" -> "09:30", "25:70" -> "23:59". Üres, ha
 * egyáltalán nincs benne szám. */
function normalizeTime(raw: string): string {
  const digits = raw.replace(/\D/g, "");
  if (!digits) return "";
  const hour = Math.min(23, Number(digits.slice(0, 2)));
  const minute = Math.min(59, Number((digits.slice(2, 4) || "0").padEnd(2, "0")));
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

/** Az óra sima szövegmező, nem `input[type=time]`: a natív mező a böngésző
 * nyelvétől függően AM/PM-et jelenít meg, ami itt kilóg és félrevezető - a HYPE
 * OS mindenhol 24 órás formátumot használ. A mentés fókuszvesztéskor (vagy
 * Enterre) történik, hogy gépelés közben ne induljon el minden karakterre. */
function TimeField({ value, onCommit }: { value: string; onCommit: (next: string) => void }) {
  const [text, setText] = useState(value);

  function commit() {
    const next = normalizeTime(text);
    setText(next || value);
    if (next && next !== value) onCommit(next);
  }

  return (
    <input
      type="text"
      inputMode="numeric"
      aria-label="Időpont"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.currentTarget.blur();
        }
      }}
      className="w-[52px] shrink-0 border-l border-border bg-transparent pl-2 text-[13px] text-text-primary focus:outline-none"
    />
  );
}

function Toggle({ on, onClick, disabled }: { on: boolean; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      disabled={disabled}
      onClick={onClick}
      className={`relative h-[18px] w-8 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
        on ? "bg-[var(--accent-solid)]" : "bg-surface-3"
      }`}
    >
      <span
        className={`absolute top-[2px] h-[14px] w-[14px] rounded-full bg-white transition-all ${on ? "left-4" : "left-[2px]"}`}
      />
    </button>
  );
}

/** Notion-stílusú dátum-választó: naptár-rács, opcionális záró dátum és
 * opcionális időpont - egy popoverben, a felhasználó által kért elrendezésben.
 *
 * A KÉT kapcsoló tényleges adatot vezérel: a "Záró dátum" kikapcsolása törli a
 * záró dátumot (a forgatás egy napos lesz), az "Időpont" kikapcsolása pedig
 * mindkét órát (a forgatás a nap egészére szól). A dátum formátum csak a
 * megjelenítést változtatja, és a böngészőben marad meg (localStorage), mert
 * ez személyes preferencia, nem a rekord adata. */
export function DateRangePicker({
  value,
  onChange,
  readOnly = false,
}: {
  value: DateRangeValue;
  onChange: (next: DateRangeValue) => void;
  readOnly?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [focusEnd, setFocusEnd] = useState(false);
  // A megjelenítési formátum a böngészőben marad meg (személyes preferencia,
  // nem a rekord adata) - az első renderen "full", majd a tárolt érték jön.
  const [format, setFormat] = useState<DateFormat>(readStoredFormat);
  const [formatOpen, setFormatOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const hasEnd = !!value.end;
  const hasTime = !!value.startTime || !!value.endTime;

  const [cursor, setCursor] = useState<Date>(() => parseISO(value.start) ?? new Date());

  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (!containerRef.current?.contains(e.target as Node)) {
        setOpen(false);
        setFormatOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  const days = useMemo(() => monthGrid(cursor), [cursor]);
  const todayISO = toISO(new Date());

  function pickDay(day: Date) {
    const iso = toISO(day);
    if (focusEnd) {
      // A záró dátum nem lehet a kezdés előtt - ilyenkor a kattintás inkább az
      // új kezdést jelenti (ugyanaz a viselkedés, mint a Notionben).
      if (value.start && iso < value.start) onChange({ ...value, start: iso });
      else onChange({ ...value, end: iso });
      return;
    }
    const next = { ...value, start: iso };
    if (next.end && next.end < iso) next.end = iso;
    onChange(next);
  }

  function toggleEnd() {
    if (hasEnd) {
      setFocusEnd(false);
      onChange({ ...value, end: "", endTime: "" });
      return;
    }
    // A záró dátum bekapcsolása után a következő kattintás a záró napot állítja
    // (a kezdés már megvan) - enélkül a kezdést írná felül.
    setFocusEnd(true);
    onChange({ ...value, end: value.start || todayISO, endTime: value.startTime });
  }

  function toggleTime() {
    if (hasTime) onChange({ ...value, startTime: "", endTime: "" });
    else onChange({ ...value, startTime: "09:00", endTime: hasEnd ? "09:00" : value.endTime });
  }

  function setToday() {
    const now = new Date();
    setCursor(now);
    const iso = toISO(now);
    const time = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    onChange({ ...value, start: iso, ...(hasTime ? { startTime: time } : {}) });
  }

  const summary = value.start
    ? `${formatDate(value.start, format)}${value.startTime ? ` ${value.startTime}` : ""}` +
      (hasEnd ? ` → ${formatDate(value.end, format)}${value.endTime ? ` ${value.endTime}` : ""}` : "")
    : "Nincs megadva";

  const fieldClass =
    "flex items-center gap-2 rounded-[var(--radius)] border px-2.5 py-1.5 text-[13px] text-text-primary transition-colors";

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        disabled={readOnly}
        onClick={() => setOpen((v) => !v)}
        className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-left text-[13px] text-text-primary transition-colors hover:bg-surface-2 disabled:opacity-50"
      >
        {summary}
      </button>

      {open && !readOnly && (
        <div className="absolute left-0 z-50 mt-1 w-[320px] rounded-[var(--radius)] border border-border bg-surface-2 p-3 shadow-lg">
          <div className="space-y-1.5">
            <div
              className={`${fieldClass} ${!focusEnd ? "border-[var(--accent-solid)] bg-bg-accent" : "border-border bg-surface-3"}`}
            >
              <button type="button" onClick={() => setFocusEnd(false)} className="flex-1 text-left">
                {formatDate(value.start, format) || "Dátum"}
              </button>
              {hasTime && (
                <TimeField
                  key={`start-${value.startTime}`}
                  value={value.startTime}
                  onCommit={(next) => onChange({ ...value, startTime: next })}
                />
              )}
            </div>
            {hasEnd && (
              <div
                className={`${fieldClass} ${focusEnd ? "border-[var(--accent-solid)] bg-bg-accent" : "border-border bg-surface-3"}`}
              >
                <button type="button" onClick={() => setFocusEnd(true)} className="flex-1 text-left">
                  {formatDate(value.end, format) || "Záró dátum"}
                </button>
                {hasTime && (
                  <TimeField
                    key={`end-${value.endTime}`}
                    value={value.endTime}
                    onCommit={(next) => onChange({ ...value, endTime: next })}
                  />
                )}
              </div>
            )}
          </div>

          <div className="mt-3 flex items-center justify-between">
            <p className="text-[13px] font-medium text-text-primary">
              {cursor.getFullYear()}. {MONTHS[cursor.getMonth()]}
            </p>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={setToday}
                className="px-1.5 text-[12px] text-text-muted transition-colors hover:text-text-primary"
              >
                {hasTime ? "Most" : "Ma"}
              </button>
              <button
                type="button"
                aria-label="Előző hónap"
                onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))}
                className="rounded p-1 text-text-muted transition-colors hover:bg-surface-3 hover:text-text-primary"
              >
                <ChevronLeft size={14} />
              </button>
              <button
                type="button"
                aria-label="Következő hónap"
                onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))}
                className="rounded p-1 text-text-muted transition-colors hover:bg-surface-3 hover:text-text-primary"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>

          <div className="mt-2 grid grid-cols-7 gap-0.5 text-center">
            {WEEKDAYS.map((w) => (
              <span key={w} className="py-1 text-[11px] text-text-muted">
                {w}
              </span>
            ))}
            {days.map((day) => {
              const iso = toISO(day);
              const inMonth = day.getMonth() === cursor.getMonth();
              const isStart = iso === value.start;
              const isEnd = hasEnd && iso === value.end;
              const inRange = hasEnd && !!value.start && iso > value.start && iso < value.end;
              const isToday = iso === todayISO;
              return (
                <button
                  key={iso}
                  type="button"
                  onClick={() => pickDay(day)}
                  className={`h-8 rounded-[var(--radius)] text-[13px] transition-colors ${
                    isStart || isEnd
                      ? "bg-[var(--accent-solid)] font-medium text-white"
                      : inRange
                        ? "bg-bg-accent text-text-accent"
                        : isToday
                          ? "bg-bg-danger text-text-danger"
                          : inMonth
                            ? "text-text-primary hover:bg-surface-3"
                            : "text-text-muted hover:bg-surface-3"
                  }`}
                >
                  {day.getDate()}
                </button>
              );
            })}
          </div>

          <div className="mt-3 space-y-1 border-t border-border pt-2">
            <div className="flex items-center justify-between py-1">
              <span className="text-[13px] text-text-primary">Záró dátum</span>
              <Toggle on={hasEnd} onClick={toggleEnd} />
            </div>
            <div className="relative flex items-center justify-between py-1">
              <span className="text-[13px] text-text-primary">Dátum formátum</span>
              <button
                type="button"
                onClick={() => setFormatOpen((v) => !v)}
                className="flex items-center gap-1 text-[13px] text-text-muted transition-colors hover:text-text-primary"
              >
                {FORMAT_LABELS[format]}
                <ChevronRight size={13} />
              </button>
              {formatOpen && (
                <div className="absolute right-0 top-full z-10 mt-1 w-[150px] rounded-[var(--radius)] border border-border bg-surface-2 p-1 shadow-lg">
                  {(Object.keys(FORMAT_LABELS) as DateFormat[]).map((f) => (
                    <button
                      key={f}
                      type="button"
                      onClick={() => {
                        setFormat(f);
                        window.localStorage.setItem(FORMAT_STORAGE_KEY, f);
                        setFormatOpen(false);
                      }}
                      className={`block w-full rounded px-2 py-1 text-left text-[13px] transition-colors hover:bg-surface-3 ${
                        f === format ? "text-text-accent" : "text-text-primary"
                      }`}
                    >
                      {FORMAT_LABELS[f]}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="flex items-center justify-between py-1">
              <span className="text-[13px] text-text-primary">Időpont</span>
              <Toggle on={hasTime} onClick={toggleTime} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
