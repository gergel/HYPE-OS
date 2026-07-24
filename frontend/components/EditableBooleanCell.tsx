"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

/** Egyetlen boolean mező be/ki kapcsolója lista-nézetekhez (táblázat-sorokban)
 * - ugyanaz a minta, mint az EditableTableCell, csak checkbox-szal, egy
 * kattintással azonnal menti az új értéket. Megállítja az eseményt, hogy a
 * kattintás ne indítsa el a sor kattintására beállított navigációt (lásd
 * RowLink). */
export function EditableBooleanCell({
  patchPath,
  field,
  value,
}: {
  patchPath: string;
  field: string;
  value: boolean | null;
}) {
  const router = useRouter();
  const [checked, setChecked] = useState(value ?? false);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    const next = !checked;
    setBusy(true);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify({ [field]: next }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setChecked(next);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <input
      type="checkbox"
      checked={checked}
      disabled={busy}
      onClick={(e) => e.stopPropagation()}
      onChange={toggle}
      className="h-4 w-4 cursor-pointer accent-[var(--text-accent)] disabled:opacity-50"
    />
  );
}
