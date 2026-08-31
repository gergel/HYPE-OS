"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { AssignableEmployee } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";

/** "Assigned To" mező - csak azok közül lehet választani, akiknek van
 * bejelentkezési joguk és hozzáférésük az /utomunka oldalhoz (lásd
 * GET /api/v1/deliverables/assignable-employees). */
export function AssignedToPicker({
  deliverableId,
  employees,
  currentId,
}: {
  deliverableId: number;
  employees: AssignableEmployee[];
  currentId: number | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleChange(value: string) {
    setBusy(true);
    try {
      // SAJÁT végpont, nem a generikus PATCH: az admin által "eltávolított"
      // mezőket a generikus PATCH némán kihagyja, és ha az
      // assigned_to_employee_id épp ilyen, a mentés szó nélkül elveszett
      // (lásd backend routes/postproduction.set_kiosztas).
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}/kiosztas`, {
        method: "PUT",
        body: JSON.stringify({ employee_id: value ? Number(value) : null }),
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
      options={[
        { value: "", label: "Nincs kijelölve" },
        ...employees.map((e) => ({ value: String(e.id), label: e.full_name })),
      ]}
      onChange={handleChange}
      className="min-w-[200px]"
    />
  );
}
