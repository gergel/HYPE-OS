"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";

/** Admin egy kattintással üríti ki a TELJES Kiadás- és Bevétel-táblát egyszerre
 * - arra kell, ha a Notionből örökölt adat annyira elcsúszott, hogy nem
 * javítgatni, hanem nulláról újraépíteni éri meg. A rájuk mutató önálló
 * dolgokat (TIG-ek, havi belsős tételek, KP forgalom, Barion-fizetések) nem
 * törli, csak eloldja - lásd backend routes/finance.torol_minden_kiadast_es_bevetelt. */
export function TorolMindenKiadastEsBevetetButton({
  kiadasDarabszam,
  bevetelDarabszam,
}: {
  kiadasDarabszam: number;
  bevetelDarabszam: number;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (
      !(await confirm(
        `Biztosan törlöd MIND a(z) ${kiadasDarabszam} Kiadást ÉS MIND a(z) ${bevetelDarabszam} Bevételt? ` +
          "Ez nem vonható vissza - csak akkor csináld, ha az egészet nulláról fel akarod tölteni újra. " +
          "A hozzájuk feltöltött bizonylatok is törlődnek; a TIG-eket, havi belsős tételeket és a KP forgalom " +
          "sorokat nem érinti, csak eloldja róluk a kapcsolatot.",
      ))
    ) {
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/finance/kiadasok-bevetelek/mind", { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      const data = await res.json().catch(() => null);
      alert(`Kész - ${data?.torolt_kiadas_db ?? 0} kiadás és ${data?.torolt_bevetel_db ?? 0} bevétel törölve.`);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (kiadasDarabszam === 0 && bevetelDarabszam === 0) return null;

  return (
    <button
      type="button"
      disabled={busy}
      onClick={handleClick}
      className="rounded-[var(--radius)] border border-text-danger/40 px-3 py-1.5 text-[13px] text-text-danger hover:bg-bg-danger disabled:opacity-50"
    >
      Összes kiadás és bevétel törlése
    </button>
  );
}
