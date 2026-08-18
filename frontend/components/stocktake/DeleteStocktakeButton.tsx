"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { useAlertDialog, useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";

/** Egy elkészült leltározás törlése - CSAK ADMINNAK jelenik meg (a backend is
 * admin szerepkört kér, lásd routes/stocktake.py).
 *
 * A leltár egy elvégzett munka nyoma: aki végigment 300 eszközön, annak az
 * eredményét ne lehessen félrekattintással eltüntetni. Ez a gomb a téves vagy
 * duplán elindított leltárak takarítására van - ezért kérdez rá, és mondja
 * ki azt is, hogy az eszközök állapotát NEM állítja vissza. */
export function DeleteStocktakeButton({ sessionId, utana = "/felszereles/leltarazas" }: { sessionId: number; utana?: string }) {
  const router = useRouter();
  const confirm = useConfirm();
  const alertDialog = useAlertDialog();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    const ok = await confirm(
      `Törlöd a(z) #${sessionId} leltározást a tételeivel együtt? Ez nem vonható vissza.\n\n` +
        "Az eszközök állapota és darabszáma marad, ahogy a leltár közben beállítottad - a törlés csak a leltár nyilvántartását szünteti meg.",
      { figyelmeztetes: "LELTÁROZÁS TÖRLÉSE", megerositoCimke: "Igen, törlöm" },
    );
    if (!ok) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/stocktake/sessions/${sessionId}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        await alertDialog(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.push(utana);
      router.refresh();
    } catch (err) {
      await alertDialog(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      disabled={busy}
      onClick={handleClick}
      className="inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
    >
      <Trash2 size={13} />
      {busy ? "Törlés…" : "Leltározás törlése"}
    </button>
  );
}
