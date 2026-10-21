"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { StocktakeSession } from "@/lib/api";

/** Új leltározás indítása - minden felvett eszközhöz felvesz egy sort a
 * jelenlegi állapotával/mennyiségével, majd az auditáló azt az oldalt kapja,
 * ahol végig tudja nézni és frissíteni (lásd services/stocktake.py start_session). */
export function StartStocktakeButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/stocktake/sessions", { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen indítás: ${detail?.detail ?? res.status}`);
        return;
      }
      const session: StocktakeSession = await res.json();
      router.push(`/felszereles/leltarazas/${session.id}`);
    } catch (err) {
      alert(`Sikertelen indítás (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      disabled={busy}
      onClick={handleClick}
      className="rounded-[var(--radius)] bg-bg-accent px-3 py-1.5 text-[13px] font-medium text-text-accent hover:opacity-90 disabled:opacity-50"
    >
      {busy ? "Indítás..." : "+ Új leltározás indítása"}
    </button>
  );
}
