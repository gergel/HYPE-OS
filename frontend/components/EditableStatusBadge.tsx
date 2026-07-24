"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SelectDropdown } from "@/components/SelectDropdown";
import { authFetch } from "@/lib/authFetch";

/** Egy állapot-jellegű (select típusú) mező színes "pill" alakban, ami
 * kattintás nélkül is azonnal legördíthető és szerkeszthető (lásd
 * SelectDropdown) - kompakt, lista-sorokba és fejlécekbe is beágyazható
 * formában (lásd DetailHeader, illetve a lista nézetek Állapot oszlopa).
 * Táblázat-sorban használva megállítja az eseményt, hogy a legördülő
 * megnyitása ne indítsa el a sor kattintására beállított navigációt (lásd
 * RowLink). */
export function EditableStatusBadge({
  patchPath,
  field,
  value,
  options,
  placeholder = "Nincs állapot",
}: {
  patchPath: string;
  field: string;
  value: string | null;
  options: string[];
  placeholder?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function onChange(next: string | null) {
    setBusy(true);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify({ [field]: next }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <span onClick={(e) => e.stopPropagation()}>
      <SelectDropdown value={value} options={options} onChange={onChange} placeholder={placeholder} disabled={busy} />
    </span>
  );
}
