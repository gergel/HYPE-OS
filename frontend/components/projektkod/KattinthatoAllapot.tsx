"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";

/** Egy kétállapotú mező (pl. "kulsos"/"egyeb" besorolás, kifizetve/nyitott
 * állapot) - egy kattintással a MÁSIK állapotra vált, ugyanabban a "pill"
 * kinézetben, mint a nem szerkeszthető StatusBadge. Ugyanaz az optimista
 * mentési minta, mint az EditableStatusBadge-nél: azonnal mutatja az új
 * értéket, hiba esetén visszaáll.
 *
 * KÜLÖN fájlban van (nem a ProjektkodBontasTablak.tsx-ben), mert az a
 * hívó oldal SZERVER-komponensként rendereli, és a lib/api.ts-ből ÉRTÉKKÉNT
 * importált ENTITY_PATHS/formatHuf a `next/headers`-t is behúzza - egy
 * kliens-komponensben ez build-hibát okozna (lásd pl. lib/diszpoSzin.ts
 * kommentje ugyanerről a csapdáról). Ez a fájl ezért önálló, kliens-biztos
 * modul, amit a szerver-komponens csak importál és behelyettesít. */
export function KattinthatoAllapot<T extends string | boolean>({
  patchPath,
  field,
  value,
  aktivErtek,
  inaktivErtek,
  aktivLabel,
  inaktivLabel,
  aktivTone,
  inaktivTone,
}: {
  patchPath: string;
  field: string;
  value: T;
  aktivErtek: T;
  inaktivErtek: T;
  aktivLabel: string;
  inaktivLabel: string;
  aktivTone: "success" | "warning" | "danger" | "neutral" | "accent";
  inaktivTone: "success" | "warning" | "danger" | "neutral" | "accent";
}) {
  const router = useRouter();
  const [ertek, setErtek] = useState(value);
  const [propErtek, setPropErtek] = useState(value);
  const [busy, setBusy] = useState(false);

  // Ha a szerver adata megjön (vagy máshonnan változik), az az igazság.
  if (value !== propErtek) {
    setPropErtek(value);
    setErtek(value);
  }

  async function valt() {
    if (busy) return;
    const uj = ertek === aktivErtek ? inaktivErtek : aktivErtek;
    const elozo = ertek;
    setErtek(uj);
    setBusy(true);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify({ [field]: uj }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setErtek(elozo);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      setErtek(elozo);
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  const aktivE = ertek === aktivErtek;
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        valt();
      }}
      disabled={busy}
      title="Kattints a váltáshoz"
      className="disabled:opacity-50"
    >
      <StatusBadge label={aktivE ? aktivLabel : inaktivLabel} tone={aktivE ? aktivTone : inaktivTone} />
    </button>
  );
}
