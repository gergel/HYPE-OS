"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { Employee } from "@/lib/api";

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
      <select
        value={selectedId}
        onChange={(e) => setSelectedId(e.target.value)}
        className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
      >
        <option value="">Válassz munkatársat vagy céget…</option>
        {candidates.map((e) => (
          <option key={`e${e.id}`} value={`e${e.id}`}>
            {e.full_name}
          </option>
        ))}
        {cegek.length > 0 && (
          <optgroup label="Számlázó cégek">
            {cegek.map((c) => (
              <option key={`v${c.id}`} value={`v${c.id}`}>
                {c.nev}
              </option>
            ))}
          </optgroup>
        )}
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
