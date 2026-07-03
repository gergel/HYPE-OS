"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

/** Egy rekord törlésére szolgáló gomb - a `path` a teljes DELETE végpont
 * (pl. /api/v1/deliverables/42). Bejelentkezés (admin/operátor szerepkör)
 * szükséges hozzá, a token a localStorage-ból megy a kérésbe. */
export function DeleteButton({ path, onDeleted }: { path: string; onDeleted?: () => void }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (!confirm("Biztosan törlöd ezt a rekordot?")) return;
    setBusy(true);
    try {
      const res = await authFetch(path, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Törlés sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      onDeleted?.();
      router.refresh();
    } catch (err) {
      alert(`Törlés sikertelen: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button type="button" onClick={handleClick} disabled={busy} className="text-text-muted hover:text-text-danger disabled:opacity-50" title="Törlés">
      ✕
    </button>
  );
}
