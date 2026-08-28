"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";

/** Admin egy kattintással üríti ki a TELJES KP forgalom-naplót - a Kiadás, a
 * Bevétel ÉS a Notionből örökölt KP forgalom táblát EGYSZERRE - arra kell, ha
 * valaki egy Notion-újraszinkronizálás előtt teljesen nulláról akarja
 * kezdeni (lásd backend routes/finance.torol_minden_mozgast). */
export function TorolMindenMozgastButton({ darabszam }: { darabszam: number }) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (
      !(await confirm(
        `Biztosan törlöd MIND a(z) ${darabszam} mozgást? Ez a Kiadás, a Bevétel ÉS a Notionből örökölt KP ` +
          "forgalom táblát is kiüríti - EZ NEM VONHATÓ VISSZA. Csak akkor csináld, ha az egészet nulláról fel " +
          "akarod tölteni újra (pl. Notionből visszaszinkronizálva).",
      ))
    ) {
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/finance/kp-naplo/mind", { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      const data = await res.json().catch(() => null);
      alert(
        `Kész - ${data?.torolt_db ?? 0} KP forgalom tétel, ${data?.torolt_kiadas_db ?? 0} kiadás és ` +
          `${data?.torolt_bevetel_db ?? 0} bevétel törölve.`,
      );
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
      Összes mozgás törlése
    </button>
  );
}
