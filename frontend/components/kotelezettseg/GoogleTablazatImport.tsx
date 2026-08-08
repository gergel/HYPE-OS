"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

const inputClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

/** Az előfizetés-táblázat behozatala a megosztott Google Táblázat linkjéből.
 *
 * Újrafuttatható: a sorok azonosítása a (név, csomag, forduló) hármas, tehát
 * a második futás nem duplikál, csak frissít - a fordulónként BEÍRT összegek
 * és a feltöltött számlák pedig érintetlenek maradnak, mert azok nem a
 * törzsadaton ülnek (lásd backend routes/kotelezettsegek.py). */
export function GoogleTablazatImport() {
  const router = useRouter();
  const [url, setUrl] = useState("");
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
        Illeszd be a táblázat megosztási linkjét. A megosztásnak legalább „Bárki a link birtokában –
        Megtekintő" szintűnek kell lennie, különben a Google nem adja ki a tartalmát. Az import
        többször is futtatható: nem duplikál, és a már beírt fordulónkénti összegekhez, feltöltött
        számlákhoz nem nyúl.
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
