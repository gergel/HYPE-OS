"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

export function CompleteStocktakeButton({ sessionId }: { sessionId: number }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (!confirm("Lezárod a leltározást? Utána a tételek már nem lesznek szerkeszthetők.")) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/stocktake/sessions/${sessionId}/complete`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen lezárás: ${detail?.detail ?? res.status}`);
        return;
      }
      router.push(`/felszereles/leltarazas/${sessionId}/eredmeny`);
    } catch (err) {
      alert(`Sikertelen lezárás (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      disabled={busy}
      onClick={handleClick}
      className="rounded-[var(--radius)] bg-bg-success px-3 py-1.5 text-[13px] font-medium text-text-success hover:opacity-90 disabled:opacity-50"
    >
      Leltározás lezárása
    </button>
  );
}
