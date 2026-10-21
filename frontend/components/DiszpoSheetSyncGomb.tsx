"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { authFetch } from "@/lib/authFetch";

/** Google Táblázat-szinkron gomb - a HYPE 2026 diszpó-táblához készült, de
 * paraméterezve más táblázat-szinkronok (pl. a Krumpelló kassza) is ezt
 * használják: a POST elindítja a háttér-szinkront, az allapot-végpont
 * kérdezgetése várja meg a végét (lásd backend services/hatter_feladat.py). */
export function DiszpoSheetSyncGomb({
  postPath = "/api/v1/diszpo-tabla/sheet-sync",
  allapotPath = "/api/v1/diszpo-tabla/sheet-sync/allapot",
  confirmSzoveg = "A szinkron a Google Táblázat tartalmára CSERÉLI a táblát (a Sheet az igazság). " +
    "Ami itt készült és a táblázatban nincs benne, az elveszik. Folytatod?",
}: {
  postPath?: string;
  allapotPath?: string;
  confirmSzoveg?: string;
} = {}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  /** A szinkron a HÁTTÉRBEN fut (lásd backend routes/diszpo_tabla.py) - az
   * indítás után az állapot-végpontot kérdezgetjük, amíg el nem készül. */
  async function varakozasAVegere() {
    for (;;) {
      await new Promise((r) => setTimeout(r, 3000));
      const res = await authFetch(allapotPath);
      if (!res.ok) continue;
      const adat = await res.json();
      if (adat.running) continue;
      if (adat.error) {
        setHiba(`A táblázat szinkronja nem sikerült: ${adat.error}`);
      } else {
        setUzenet(adat.uzenet ?? "Kész.");
        router.refresh();
      }
      return;
    }
  }

  async function indit() {
    if (!window.confirm(confirmSzoveg)) {
      return;
    }
    setBusy(true);
    setHiba(null);
    setUzenet(null);
    try {
      const res = await authFetch(postPath, { method: "POST" });
      const adat = await res.json().catch(() => null);
      if (!res.ok) {
        setHiba(adat?.detail ?? `Sikertelen szinkron (HTTP ${res.status})`);
        return;
      }
      await varakozasAVegere();
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
