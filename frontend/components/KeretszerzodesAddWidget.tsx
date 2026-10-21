"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { Employee } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";

/** Keretszerződés felvétele egy MUNKATÁRSSAL vagy egy CÉGGEL.
 *
 * A cégadatokat a backend automatikusan átmásolja a kiválasztott fél saját
 * mezőiből (lásd routes/contracts.py create_keretszerzodes).
 *
 * A céggel kötött keretszerződés az összes olyan ember munkáját fedi, akinél a
 * projekten ezt a céget jelöltük meg számlázó félként - így az általa küldött
 * emberektől nem kell külön eseti szerződést kérni. */
export function KeretszerzodesAddWidget({
  candidates,
  cegek = [],
}: {
  candidates: Employee[];
  cegek?: { id: number; nev: string }[];
}) {
  const router = useRouter();
  // A választott fél kulcsa: "e12" (ember) vagy "v3" (cég).
  const [selectedId, setSelectedId] = useState<string>("");
  const [busy, setBusy] = useState(false);

  async function handleAdd() {
    if (!selectedId) return;
    setBusy(true);
    try {
      const azonosito = Number(selectedId.slice(1));
      const res = await authFetch("/api/v1/contracts/keretszerzodes", {
        method: "POST",
        body: JSON.stringify(
          selectedId.startsWith("v") ? { vallalkozas_id: azonosito } : { employee_id: azonosito },
        ),
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
        value={selectedId || null}
        options={[
          ...candidates.map((e) => ({ value: `e${e.id}`, label: e.full_name, group: "Munkatársak" })),
          ...cegek.map((c) => ({ value: `v${c.id}`, label: c.nev, group: "Számlázó cégek" })),
        ]}
        onChange={setSelectedId}
        placeholder="Válassz munkatársat vagy céget…"
        className="min-w-[260px]"
      />
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
