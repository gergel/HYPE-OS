"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { selectColor } from "@/lib/selectColor";

/** Egy állapot-jellegű (select típusú) mező színes "pill" alakban, ami
 * kattintás nélkül is azonnal legördíthető és szerkeszthető - ugyanaz a
 * minta, mint az EditableDetailGrid select-mezője, de kompakt, lista-
 * sorokba és fejlécekbe is beágyazható formában (lásd DetailHeader, illetve
 * a lista nézetek Állapot oszlopa). Táblázat-sorban használva megállítja az
 * eseményt, hogy a legördülő megnyitása ne indítsa el a sor kattintására
 * beállított navigációt (lásd RowLink). */
export function EditableStatusBadge({
  patchPath,
  field,
  value,
  options,
  placeholder = "Nincs állapot",
}: {
  patchPath: string;
  field: string;
  value: string | null;
  options: string[];
  placeholder?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function onChange(next: string) {
    setBusy(true);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify({ [field]: next || null }) });
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

  const color = value ? selectColor(value) : { bg: "var(--surface-3)", text: "var(--text-muted)" };

  return (
    <span
      onClick={(e) => e.stopPropagation()}
      className="inline-flex items-center gap-1.5 rounded-full py-1 pl-2.5 pr-1.5 text-[12px] font-medium"
      style={{ background: color.bg, color: color.text, opacity: busy ? 0.6 : 1 }}
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color.text }} />
      <select
        value={value ?? ""}
        disabled={busy}
        onChange={(e) => onChange(e.target.value)}
        className="cursor-pointer appearance-none bg-transparent pr-1 text-[12px] font-medium outline-none"
        style={{ color: color.text }}
      >
        <option value="" className="text-black">
          {placeholder}
        </option>
        {options.map((opt) => (
          <option key={opt} value={opt} className="text-black">
            {opt}
          </option>
        ))}
      </select>
    </span>
  );
}
