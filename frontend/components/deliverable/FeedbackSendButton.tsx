"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";

/** "Visszajelzés küldése" gomb - a felhasználó által küldött Notion
 * automatizmus portolása (lásd services/deliverable_actions.send_visszajelzes):
 * új Visszajelzés rekordot hoz létre a jelenlegi értékelésekből, majd kiüríti
 * azokat az anyagon a következő körhöz. */
export function FeedbackSendButton({ deliverableId }: { deliverableId: number }) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (!(await confirm("Biztos küldesz visszajelzést?"))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}/kuldes-visszajelzes`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
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
      Visszajelzés küldése
    </button>
  );
}
