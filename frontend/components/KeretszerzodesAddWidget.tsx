"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { Employee } from "@/lib/api";

/** Egy meglévő crew tag (bármelyik tipus, a belsős is) felvétele a
 * Keretszerződések közé - a cégadatokat a backend automatikusan átmásolja az
 * Employee saját mezőiből (lásd routes/contracts.py create_keretszerzodes). */
export function KeretszerzodesAddWidget({ candidates }: { candidates: Employee[] }) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<number | "">("");
  const [busy, setBusy] = useState(false);

  async function handleAdd() {
    if (!selectedId) return;
    setBusy(true);
    try {
      const res = await authFetch("/api/v1/contracts/keretszerzodes", {
        method: "POST",
        body: JSON.stringify({ employee_id: selectedId }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen hozzáadás: ${detail?.detail ?? res.status}`);
        return;
      }
      setSelectedId("");
      router.refresh();
    } catch (err) {
      alert(`Sikertelen hozzáadás (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 rounded-[var(--radius)] border border-border bg-surface-3 p-3">
      <select
        value={selectedId}
        onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : "")}
        className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
      >
        <option value="">Válassz munkatársat…</option>
        {candidates.map((e) => (
          <option key={e.id} value={e.id}>
            {e.full_name}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={handleAdd}
        disabled={busy || !selectedId}
        className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-2 disabled:opacity-50"
      >
        {busy ? "Hozzáadás…" : "Keretszerződés felvétele"}
      </button>
    </div>
  );
}
