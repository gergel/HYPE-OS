"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";

/** Admin egy kattintással üríti ki a TELJES "KP forgalom" táblát - arra kell,
 * ha a Notionből örökölt adat annyira elcsúszott, hogy nem javítgatni, hanem
 * nulláról újraépíteni éri meg. A hozzájuk kötött Kiadás-sorokat nem érinti
 * (lásd backend routes/finance.torol_minden_kp_forgalmat). */
export function TorolMindenKpForgalmatButton({ darabszam }: { darabszam: number }) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (
      !(await confirm(
        `Biztosan törlöd MIND a(z) ${darabszam} KP forgalom tételt? Ez nem vonható vissza - csak akkor csináld, ` +
          "ha az egészet nulláról fel akarod tölteni újra. A kiadás-/bevétel-sorokat nem érinti, csak ezt a táblát üríti.",
      ))
    ) {
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/finance/kp-forgalom/mind", { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      const data = await res.json().catch(() => null);
      alert(`Kész - ${data?.torolt_db ?? 0} tétel törölve.`);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (darabszam === 0) return null;

  return (
    <button
      type="button"
      disabled={busy}
      onClick={handleClick}
      className="rounded-[var(--radius)] border border-text-danger/40 px-3 py-1.5 text-[13px] text-text-danger hover:bg-bg-danger disabled:opacity-50"
    >
      Összes tétel törlése
    </button>
  );
}
