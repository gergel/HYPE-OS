"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type Option = { id: number; label: string; href?: string };

/** Egyetlen (nem many-to-many) relation mező kiválasztása, pl. Project
 * 'Szerződés készítés' (Employee) vagy 'Alvállakozó keretszerződés' (Contract)
 * mezője - legördülőből választva egy JSON body-t küld a megadott path-ra
 * (POST vagy PATCH), amit a backend feldolgoz (lásd projects.py). */
export function SingleRelationPicker({
  path,
  method = "POST",
  bodyKey,
  currentId,
  currentLabel,
  options,
  actionLabel = "Kiválasztás",
  emptyText = "Nincs kiválasztva.",
  allowClear = true,
}: {
  path: string;
  method?: "POST" | "PATCH";
  bodyKey: string;
  currentId?: number | null;
  currentLabel?: string | null;
  options: Option[];
  actionLabel?: string;
  emptyText?: string;
  allowClear?: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState("");

  const current = currentId ? options.find((o) => o.id === currentId) : undefined;

  async function submit(id: number | null) {
    setBusy(true);
    try {
      const res = await authFetch(path, { method, body: JSON.stringify({ [bodyKey]: id }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="mb-2 text-[13px] text-text-secondary">
        {current ? (
          current.href ? (
            <a href={current.href} className="text-text-accent hover:underline">
              {current.label}
            </a>
          ) : (
            current.label
          )
        ) : currentLabel ? (
          currentLabel
        ) : (
          <span className="text-text-muted">{emptyText}</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
        >
          <option value="">Válassz...</option>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          disabled={!selected || busy}
          onClick={() => submit(Number(selected))}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          {actionLabel}
        </button>
        {current && allowClear && (
          <button
            type="button"
            disabled={busy}
            onClick={() => submit(null)}
            className="text-[13px] text-text-muted hover:text-text-danger disabled:opacity-50"
          >
            Törlés
          </button>
        )}
      </div>
    </div>
  );
}
