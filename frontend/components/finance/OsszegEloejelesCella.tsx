"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { formatHuf } from "@/lib/penz";

/** Egy ELŐJELES összeg-cella a KP forgalom naplóhoz: egy mező a korábbi Be/Ki
 * kettő helyett - amit beírunk, negatívan KIADÁS, pozitívan (vagy nullán)
 * BEVÉTEL lesz belőle. A háttérben ez a `forgalom` mezőt is beállítja, hogy a
 * kassza számítása (services/kassza.py) ugyanígy lássa az irányt. */
export function OsszegEloejelesCella({ patchPath, ertek }: { patchPath: string; ertek: number }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(ertek));
  const [displayValue, setDisplayValue] = useState(ertek);
  const [busy, setBusy] = useState(false);

  async function commit() {
    const nyers = draft.trim().replace(/\s/g, "").replace(",", ".");
    const next = nyers === "" ? 0 : Number(nyers);
    if (!Number.isFinite(next)) {
      setEditing(false);
      return;
    }
    const elozo = displayValue;
    setDisplayValue(next);
    setEditing(false);
    setBusy(true);
    try {
      const res = await authFetch(patchPath, {
        method: "PATCH",
        body: JSON.stringify({ osszeg: Math.abs(next), forgalom: next < 0 ? "kiadas" : "bevetel" }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setDisplayValue(elozo);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      setDisplayValue(elozo);
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (!editing) {
    return (
      <span
        role="button"
        tabIndex={0}
        onClick={(e) => {
          e.stopPropagation();
          setDraft(String(displayValue));
          setEditing(true);
        }}
        className={`-mx-1 cursor-text rounded px-1 py-0.5 hover:bg-surface-3 ${
          displayValue < 0 ? "text-text-orange" : "text-text-teal"
        }`}
      >
        {displayValue < 0 ? "−" : "+"}
        {formatHuf(Math.abs(displayValue))}
      </span>
    );
  }

  return (
    <input
      autoFocus
      disabled={busy}
      type="number"
      value={draft}
      placeholder="negatív = kiadás"
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Escape") setEditing(false);
        if (e.key === "Enter") commit();
      }}
      className="w-full min-w-[11ch] rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
    />
  );
}
