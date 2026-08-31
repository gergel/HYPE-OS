"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import type { AssignableEmployee } from "@/lib/api";
import { KeresosSelect } from "@/components/KeresosSelect";

/** Kiosztás - TÖBB ember is lehet (a felhasználó kérése). A kiosztottak
 * sorban, eltávolító gombbal; alattuk a hozzáadó választó, amiben csak azok
 * szerepelnek, akiknek van bejelentkezési joguk és hozzáférésük az /utomunka
 * oldalhoz (lásd GET /api/v1/deliverables/assignable-employees).
 *
 * SAJÁT végpontra ment (PUT /kiosztas), nem a generikus PATCH-re: az admin
 * által "eltávolított" mezőket a generikus PATCH némán kihagyja, és a mentés
 * szó nélkül elveszett volna (lásd backend routes/postproduction.set_kiosztas). */
export function AssignedToPicker({
  deliverableId,
  employees,
  currentIds,
}: {
  deliverableId: number;
  employees: AssignableEmployee[];
  currentIds: number[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  // Optimista lista: a mentés után a router.refresh() hozza a szerver
  // állapotát, addig ezt mutatjuk, hogy a hozzáadás azonnal látsszon.
  const [ids, setIds] = useState(currentIds);

  const nevek = new Map(employees.map((e) => [e.id, e.full_name]));

  async function mentes(ujIds: number[]) {
    const elozo = ids;
    setIds(ujIds);
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}/kiosztas`, {
        method: "PUT",
        body: JSON.stringify({ employee_ids: ujIds }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setIds(elozo);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      setIds(elozo);
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  const valaszthatok = employees.filter((e) => !ids.includes(e.id));

  return (
    <div className="space-y-2">
      {ids.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {ids.map((id) => (
            <span
              key={id}
              className="inline-flex items-center gap-1 rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1 text-[13px] text-text-primary"
            >
              {nevek.get(id) ?? `#${id}`}
              <button
                type="button"
                disabled={busy}
                onClick={() => void mentes(ids.filter((i) => i !== id))}
                aria-label="Eltávolítás a kiosztásból"
                className="text-text-muted hover:text-text-danger disabled:opacity-50"
              >
                <X size={13} />
              </button>
            </span>
          ))}
        </div>
      )}
      <KeresosSelect
        disabled={busy}
        value=""
        placeholder={ids.length === 0 ? "Nincs kijelölve - válassz…" : "+ További ember hozzáadása…"}
        options={valaszthatok.map((e) => ({ value: String(e.id), label: e.full_name }))}
        onChange={(value) => {
          if (value) void mentes([...ids, Number(value)]);
        }}
        className="min-w-[200px]"
      />
    </div>
  );
}
