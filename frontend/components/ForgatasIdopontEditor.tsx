"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { Card } from "@/components/Card";
import { CalendarClock } from "lucide-react";

type Draft = {
  forgatas_datuma: string;
  forgatas_kezdes_ido: string;
  forgatas_datuma_vege: string;
  forgatas_veg_ido: string;
};

const inputClass =
  "rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none disabled:opacity-50";

/** A forgatás ideje EGY helyen: kezdő dátum + óra, záró dátum + óra.
 *
 * Ez ugyanaz a négy mező, ami a projekten külön-külön is létezik
 * (forgatas_datuma / forgatas_kezdes_ido / forgatas_datuma_vege /
 * forgatas_veg_ido), de itt együtt szerkeszthető, mert egy dolgot írnak le:
 * mikortól meddig tart a forgatás. Ez az adat hajtja a Diszpó naptár nézetet
 * és a diszpó tárgyát is, és a HYPE CALENDAR szinkron is ezt tölti
 * (lásd backend services/google_calendar.py).
 *
 * A záró dátum ELHAGYHATÓ: üresen a forgatás egy napos. Az időpontok is
 * elhagyhatók - üresen a nap egészére szól, ahogy eddig is. */
export function ForgatasIdopontEditor({
  patchPath,
  initial,
  readOnly = false,
}: {
  patchPath: string;
  initial: Draft;
  readOnly?: boolean;
}) {
  const router = useRouter();
  const [draft, setDraft] = useState<Draft>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save(next: Draft) {
    setDraft(next);
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const res = await authFetch(patchPath, {
        method: "PATCH",
        body: JSON.stringify({
          forgatas_datuma: next.forgatas_datuma || null,
          forgatas_kezdes_ido: next.forgatas_kezdes_ido || null,
          forgatas_datuma_vege: next.forgatas_datuma_vege || null,
          forgatas_veg_ido: next.forgatas_veg_ido || null,
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

  function update<K extends keyof Draft>(key: K, value: string) {
    save({ ...draft, [key]: value });
  }

  const tobbNapos = !!draft.forgatas_datuma_vege && draft.forgatas_datuma_vege !== draft.forgatas_datuma;

  return (
    <Card title="Forgatás időpontja" icon={CalendarClock}>
      <div className="space-y-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-16 text-[12px] text-text-muted">Kezdés</span>
          <input
            type="date"
            value={draft.forgatas_datuma}
            disabled={readOnly || busy}
            onChange={(e) => update("forgatas_datuma", e.target.value)}
            className={inputClass}
          />
          <input
            type="time"
            value={draft.forgatas_kezdes_ido}
            disabled={readOnly || busy}
            onChange={(e) => update("forgatas_kezdes_ido", e.target.value)}
            className={inputClass}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-16 text-[12px] text-text-muted">Vége</span>
          <input
            type="date"
            value={draft.forgatas_datuma_vege}
            disabled={readOnly || busy}
            onChange={(e) => update("forgatas_datuma_vege", e.target.value)}
            className={inputClass}
          />
          <input
            type="time"
            value={draft.forgatas_veg_ido}
            disabled={readOnly || busy}
            onChange={(e) => update("forgatas_veg_ido", e.target.value)}
            className={inputClass}
          />
        </div>
        <p className="text-[12px] text-text-muted">
          {tobbNapos ? "Több napos forgatás." : "A záró dátumot üresen hagyva egy napos a forgatás."} Az időpont
          elhagyható - a naptárból szinkronizált eseményeknél magától kitöltődik.
        </p>
        {error && <p className="text-[12px] text-text-danger">{error}</p>}
        {saved && !error && <p className="text-[12px] text-text-success">Mentve.</p>}
      </div>
    </Card>
  );
}
