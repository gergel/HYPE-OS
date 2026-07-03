"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

/** Egy Notion button-automatizmust portoló, egy kattintásos backend akció (pl.
 * Feldarabolás, Utómunka létrehozása) - POST a megadott útvonalra, majd vagy
 * frissíti az oldalt, vagy (ha a válasz egy új rekordot ad vissza) átirányít
 * annak részletnézetére. */
export function ActionButton({
  path,
  label,
  confirmMessage,
  redirectTo,
}: {
  path: string;
  label: string;
  confirmMessage?: string;
  redirectTo?: (result: Record<string, unknown>) => string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (confirmMessage && !confirm(confirmMessage)) return;
    setBusy(true);
    try {
      const res = await authFetch(path, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      const data = await res.json().catch(() => null);
      if (redirectTo && data) {
        router.push(redirectTo(data));
      } else {
        router.refresh();
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
    >
      {busy ? "Folyamatban…" : label}
    </button>
  );
}
