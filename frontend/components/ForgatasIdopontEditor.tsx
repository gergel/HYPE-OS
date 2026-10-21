"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarClock } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { Card } from "@/components/Card";
import { DateRangePicker, type DateRangeValue } from "@/components/DateRangePicker";

/** A forgatás ideje EGY mezőként: kezdő dátum, opcionális záró dátum, és
 * opcionális időpont - a felhasználó által kért Notion-szerű választóval
 * (lásd DateRangePicker).
 *
 * A négy DB-oszlop (forgatas_datuma / forgatas_kezdes_ido /
 * forgatas_datuma_vege / forgatas_veg_ido) mögötte marad, de a felületen nem
 * külön mezőkként jelenik meg, mert egy dolgot írnak le: mikortól meddig tart
 * a forgatás. Ez az adat hajtja a Diszpó naptár nézetet és a diszpó tárgyát is,
 * és a HYPE CALENDAR szinkron is ezt tölti (lásd backend
 * services/google_calendar.py). */
export function ForgatasIdopontEditor({
  patchPath,
  initial,
  readOnly = false,
}: {
  patchPath: string;
  initial: DateRangeValue;
  readOnly?: boolean;
}) {
  const router = useRouter();
  const [value, setValue] = useState<DateRangeValue>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save(next: DateRangeValue) {
    setValue(next);
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const res = await authFetch(patchPath, {
        method: "PATCH",
        body: JSON.stringify({
          forgatas_datuma: next.start || null,
          forgatas_kezdes_ido: next.startTime || null,
          forgatas_datuma_vege: next.end || null,
          forgatas_veg_ido: next.endTime || null,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setError(detail?.detail ?? `HTTP ${res.status}`);
        return;
      }
      setSaved(true);
      router.refresh();
    } catch (err) {
      setError(`Hálózati hiba: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Forgatás dátuma" icon={CalendarClock}>
      <DateRangePicker value={value} onChange={save} readOnly={readOnly || busy} />
      {error && <p className="mt-2 text-[12px] text-text-danger">{error}</p>}
      {saved && !error && <p className="mt-2 text-[12px] text-text-success">Mentve.</p>}
    </Card>
  );
}
