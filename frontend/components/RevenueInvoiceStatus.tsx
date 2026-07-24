"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { StatusBadge } from "@/components/StatusBadge";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** A megrendelői számla köztes állapotai: Nincs kiállítva -> Számla kiállítva
 * -> Kifizetve (lásd backend Revenue.szamla_kiallitva_datuma) - kattintásra
 * lép a következő állapotba, a számla tényleges kiállítása a külső
 * számlázási rendszerben történik, itt csak a dátumokat rögzítjük. */
export function RevenueInvoiceStatus({
  patchPath,
  szamlaKiallitva,
  fizetve,
}: {
  patchPath: string;
  szamlaKiallitva: string | null;
  fizetve: string | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function patch(field: string, value: string) {
    setBusy(true);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify({ [field]: value }) });
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

  if (fizetve) {
    return <StatusBadge label="Kifizetve" tone="success" />;
  }
  if (szamlaKiallitva) {
    return (
      <button
        type="button"
        disabled={busy}
        onClick={(e) => {
          e.stopPropagation();
          patch("fizetes_datuma", today());
        }}
        className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        Számla kiállítva - Kifizetve jelölés
      </button>
    );
  }
  return (
    <button
      type="button"
      disabled={busy}
      onClick={(e) => {
        e.stopPropagation();
        patch("szamla_kiallitva_datuma", today());
      }}
      className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
    >
      Számla kiállítása
    </button>
  );
}
