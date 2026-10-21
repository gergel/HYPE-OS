"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Flag } from "lucide-react";
import { authFetch } from "@/lib/authFetch";

/** PRIORITÁS kapcsoló az utómunka adatlap fejlécében (a felhasználó kérése):
 * bekapcsolva az anyag kártyája piros körvonalat kap az Utómunka táblán,
 * amíg kész/kiküldhető állapotba nem kerül - a vágó innen tudja, mivel
 * kezdjen, min dolgozzon elsőként. */
export function PrioritasKapcsolo({ deliverableId, kezdeti }: { deliverableId: number; kezdeti: boolean }) {
  const router = useRouter();
  // Optimista: a gomb azonnal vált, hiba esetén visszaáll.
  const [bekapcsolva, setBekapcsolva] = useState(kezdeti);

  async function valt() {
    const uj = !bekapcsolva;
    setBekapcsolva(uj);
    try {
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}`, {
        method: "PATCH",
        body: JSON.stringify({ prioritas: uj }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setBekapcsolva(!uj);
        alert(`A prioritás átállítása nem sikerült: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      setBekapcsolva(!uj);
      alert(`A prioritás átállítása nem sikerült (hálózati hiba): ${err}`);
    }
  }

  return (
    <button
      type="button"
      onClick={() => void valt()}
      title={
        bekapcsolva
          ? "Prioritás kikapcsolása - a kártya piros kiemelése lekerül"
          : "Prioritás bekapcsolása - a kártya piros körvonalat kap a táblán, a vágó ezzel kezdjen"
      }
      className={`flex items-center gap-1.5 rounded-[var(--radius)] border px-3 py-1.5 text-[12.5px] font-medium transition-colors ${
        bekapcsolva
          ? "border-red-600 bg-red-600/10 text-red-500 hover:bg-red-600/20"
          : "border-border text-text-secondary hover:bg-surface-3"
      }`}
    >
      <Flag className="h-3.5 w-3.5" />
      {bekapcsolva ? "Prioritás BE" : "Prioritás"}
    </button>
  );
}
