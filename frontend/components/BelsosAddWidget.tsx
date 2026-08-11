"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { Employee } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";

/** Bármelyik crew tag felvétele a Belsősök közé - a tipus mezőt "belsos"-ra
 * állítja (lásd Vágók oldal, ahol a tipus=="vago" jelöli ki a listát; itt
 * ugyanez a szűrés, csak az admin bármikor át tud sorolni valakit ide). */
export function BelsosAddWidget({ candidates }: { candidates: Employee[] }) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<number | "">("");
  const [busy, setBusy] = useState(false);

  async function handleAdd() {
    if (!selectedId) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/crew/${selectedId}`, {
        method: "PATCH",
        body: JSON.stringify({ tipus: "belsos" }),
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
      <KeresosSelect
        value={selectedId === "" ? null : String(selectedId)}
        options={candidates.map((e) => ({ value: String(e.id), label: e.full_name }))}
        onChange={(ertek) => setSelectedId(Number(ertek))}
        placeholder="Válassz munkatársat…"
        className="min-w-[220px]"
      />
      <button
        type="button"
        onClick={handleAdd}
        disabled={busy || !selectedId}
        className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-2 disabled:opacity-50"
      >
        {busy ? "Hozzáadás…" : "Hozzáadás a Belsősökhöz"}
      </button>
    </div>
  );
}
