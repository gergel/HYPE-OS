"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

const inputClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

//: Az E-Rezsi Google Táblázat megosztási linkje - előre kitöltve, hogy a
//: szinkron egyetlen kattintás legyen (a mező átírható, ha egyszer másik
//: táblázatra költözik az adat).
const ALAPERTELMEZETT_URL =
  "https://docs.google.com/spreadsheets/d/1e18q6eTbvnHI9ZZT49zGaUDig5aFRAyLM66_VRGg1M4/edit";

/** Az előfizetés-táblázat TÜKRE a megosztott Google Táblázat linkjéből.
 *
 * Újrafuttatható és egy-az-egyben: a sorok azonosítása a (név, csomag)
 * páros, a második futás nem duplikál, csak frissít - és ami a táblázatból
 * kikerült, az innen is törlődik (lásd backend routes/kotelezettsegek.py). */
export function GoogleTablazatImport() {
  const router = useRouter();
  const [url, setUrl] = useState(ALAPERTELMEZETT_URL);
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  async function indit() {
    if (!url.trim()) {
      setHiba("Illeszd be a táblázat linkjét.");
      return;
    }
    setBusy(true);
    setHiba(null);
    setUzenet(null);
    try {
      const res = await authFetch("/api/v1/kotelezettsegek/import-google-tablazat", {
        method: "POST",
        body: JSON.stringify({ url: url.trim() }),
      });
      const adat = await res.json().catch(() => null);
      if (!res.ok) {
        setHiba(adat?.detail ?? `Sikertelen import (HTTP ${res.status})`);
        return;
      }
      setUzenet(adat?.uzenet ?? "Kész.");
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen import (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-[12.5px] text-text-muted">
        A szinkron a táblázat TÜKRE: többször futtatható, nem duplikál - frissíti a meglévő
        sorokat, és ami a táblázatból kikerült, azt innen is törli. A megosztásnak legalább „Bárki
        a link birtokában – Megtekintő&quot; szintűnek kell lennie.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://docs.google.com/spreadsheets/d/…"
          disabled={busy}
          className={`${inputClass} max-w-[520px] flex-1`}
        />
        <button
          type="button"
          onClick={indit}
          disabled={busy}
          className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Behozatal…" : "Behozatal"}
        </button>
      </div>
      {uzenet && <p className="text-[12.5px] text-text-success">{uzenet}</p>}
      {hiba && <p className="text-[12.5px] text-text-danger">{hiba}</p>}
    </div>
  );
}
