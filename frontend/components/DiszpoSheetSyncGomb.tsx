"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { authFetch } from "@/lib/authFetch";

/** A HYPE 2026 tábla szinkronja a megosztott Google Táblázattal - egy
 * gombbal, a felületről (lásd backend routes/diszpo_tabla.py "sheet-sync").
 * Munkalaponként CSERÉLI a tartalmat (a Sheet az igazság), a kézzel
 * beállított oszlop-ember kötések megmaradnak. */
export function DiszpoSheetSyncGomb() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  async function indit() {
    if (!window.confirm(
      "A szinkron a Google Táblázat tartalmára CSERÉLI a táblát (a Sheet az igazság). " +
      "Ami itt készült és a táblázatban nincs benne, az elveszik. Folytatod?",
    )) {
      return;
    }
    setBusy(true);
    setHiba(null);
    setUzenet(null);
    try {
      const res = await authFetch("/api/v1/diszpo-tabla/sheet-sync", { method: "POST" });
      const adat = await res.json().catch(() => null);
      if (!res.ok) {
        setHiba(adat?.detail ?? `Sikertelen szinkron (HTTP ${res.status})`);
        return;
      }
      setUzenet(adat?.uzenet ?? "Kész.");
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen szinkron (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={indit}
        disabled={busy}
        className="inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        <RefreshCw size={13} className={busy ? "animate-spin" : ""} />
        {busy ? "Szinkron a Google Táblázattal…" : "Szinkron a Google Táblázattal"}
      </button>
      {uzenet && <p className="text-[12.5px] text-text-success">{uzenet}</p>}
      {hiba && <p className="text-[12.5px] text-text-danger">{hiba}</p>}
    </div>
  );
}
