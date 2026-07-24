"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type InputType = "text" | "number" | "date";

/** Egy mező helyben szerkeszthető cellája LISTA-nézetekhez (táblázat-sorokban)
 * - ugyanaz a kattintásra-szerkeszthető interakció, mint a részletnézet
 * EditableDetailGrid-jén (lásd EditableCell), csak <span>/<input> alapon,
 * hogy bármelyik DataTable oszlop render függvényébe behelyettesíthető
 * legyen. Megállítja az eseményt, hogy a szerkesztésbe lépés/gépelés ne
 * indítsa el a sor kattintására beállított navigációt (lásd RowLink). */
export function EditableTableCell({
  patchPath,
  field,
  value,
  type = "text",
  placeholder = "Üres",
}: {
  patchPath: string;
  field: string;
  value: string | number | null;
  type?: InputType;
  placeholder?: string;
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value === null ? "" : String(value));
  const [busy, setBusy] = useState(false);

  async function save(next: unknown) {
    setBusy(true);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify({ [field]: next }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setEditing(false);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  function commit() {
    save(type === "number" ? (draft ? Number(draft) : null) : draft || null);
  }

  if (!editing) {
    return (
      <span
        role="button"
        tabIndex={0}
        onClick={(e) => {
          e.stopPropagation();
          setEditing(true);
        }}
        className="-mx-1 cursor-text rounded px-1 py-0.5 hover:bg-surface-3"
      >
        {value !== null && value !== "" ? String(value) : <span className="text-text-muted italic">{placeholder}</span>}
      </span>
    );
  }

  return (
    <input
      autoFocus
      disabled={busy}
      type={type}
      value={draft}
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Escape") setEditing(false);
        if (e.key === "Enter") commit();
      }}
      className="w-full min-w-[8ch] rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
    />
  );
}
