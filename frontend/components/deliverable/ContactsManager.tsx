"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { DeliverableContact } from "@/lib/api";

/** "Megrendelői kontaktok" - kiknek kell majd kiküldeni a kész anyagot (a
 * megrendeloi_email_cimek formula-mező ebből számolódik újra, lásd
 * services/deliverable_actions.set_contacts). */
export function ContactsManager({
  deliverableId,
  current,
  options,
}: {
  deliverableId: number;
  current: DeliverableContact[];
  options: DeliverableContact[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState("");

  const currentIds = current.map((c) => c.id);
  const available = options.filter((o) => !currentIds.includes(o.id));

  async function save(ids: number[]) {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/deliverables/${deliverableId}/contacts`, {
        method: "PUT",
        body: JSON.stringify({ contact_ids: ids }),
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
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        {current.length === 0 && <p className="text-[13px] text-text-muted">Nincs megrendelői kontakt hozzárendelve.</p>}
        {current.map((c) => (
          <span key={c.id} className="flex items-center gap-1.5 rounded-[var(--radius)] bg-surface-3 px-2.5 py-1 text-[13px]">
            {c.full_name}
            {c.email && <span className="text-text-muted">({c.email})</span>}
            <button
              type="button"
              disabled={busy}
              onClick={() => save(currentIds.filter((id) => id !== c.id))}
              className="text-text-muted hover:text-text-danger disabled:opacity-50"
              title="Leválasztás"
            >
              ✕
            </button>
          </span>
        ))}
      </div>
      {available.length > 0 ? (
        <div className="flex items-center gap-2">
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
          >
            <option value="">Válassz...</option>
            {available.map((o) => (
              <option key={o.id} value={o.id}>
                {o.full_name}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={!selected || busy}
            onClick={() => {
              save([...currentIds, Number(selected)]);
              setSelected("");
            }}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            Hozzáadás
          </button>
        </div>
      ) : (
        <p className="text-[12px] text-text-muted">
          {options.length === 0 ? "Ehhez az ügyfélhez nincs felvett kontakt." : "Minden elérhető kontakt már hozzá van rendelve."}
        </p>
      )}
    </div>
  );
}
