"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { KeresosSelect } from "@/components/KeresosSelect";

/** EGY munkatársra mutató (egyszemélyes idegenkulcs) mező szerkesztője -
 * PATCH-eli a megadott mezőt (id vagy null), minta:
 * components/deliverable/AssignedToPicker.tsx, csak általánosítva (bármely
 * patchPath + mezőnév). A kínálatot a HÍVÓ szűri: a HYPE TO-DO LIST
 * "Ellenőrzés felelős" mezőjénél pl. csak azok választhatók, akik látják az
 * oldalt (lásd getLathatjakAzOldalt), ugyanúgy, mint a Felelős M2M-nél. */
export function EmployeeFkPicker({
  patchPath,
  field,
  currentId,
  options,
  emptyLabel = "Nincs kijelölve",
  className = "",
}: {
  patchPath: string;
  field: string;
  currentId: number | null;
  options: { id: number; label: string }[];
  emptyLabel?: string;
  className?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleChange(value: string) {
    setBusy(true);
    try {
      const res = await authFetch(patchPath, {
        method: "PATCH",
        body: JSON.stringify({ [field]: value ? Number(value) : null }),
      });
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
    <KeresosSelect
      disabled={busy}
      value={currentId === null || currentId === undefined ? "" : String(currentId)}
      options={[{ value: "", label: emptyLabel }, ...options.map((o) => ({ value: String(o.id), label: o.label }))]}
      onChange={handleChange}
      className={className || "min-w-[200px]"}
    />
  );
}
