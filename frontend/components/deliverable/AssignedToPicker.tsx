"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { AssignableEmployee } from "@/lib/api";

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
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}`, {
        method: "PATCH",
        body: JSON.stringify({ assigned_to_employee_id: value ? Number(value) : null }),
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
    <select
      disabled={busy}
      value={currentId ?? ""}
      onChange={(e) => handleChange(e.target.value)}
      className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
    >
      <option value="">Nincs kijelölve</option>
      {employees.map((e) => (
        <option key={e.id} value={e.id}>
          {e.full_name}
        </option>
      ))}
    </select>
  );
}
