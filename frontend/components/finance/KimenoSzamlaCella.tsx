"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2, Upload } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { StopClickPropagation } from "@/components/StopClickPropagation";
import { authFetch } from "@/lib/authFetch";

/** A KIMENŐ (megrendelői) számla PDF-je egy bevétel-sorhoz. Maga a számla
 * külső számlázó rendszerben készül - ide azért kerül fel, hogy a havi
 * számla-csomagban (lásd SzamlaCsomagLetoltes) a kimenő számlák is benne
 * legyenek, ne csak a TIG-ekhez feltöltött bejövők. Bevételenként egy fájl: az
 * újabb feltöltés lecseréli a korábbit. */
export function KimenoSzamlaCella({
  revenueId,
  filename,
  url,
  canEdit,
  canDelete,
}: {
  revenueId: number;
  filename: string | null;
  url: string | null;
  canEdit: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function feltolt(file: File) {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await authFetch(`/api/v1/finance/revenues/${revenueId}/szamla`, { method: "POST", body: fd });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen feltöltés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen feltöltés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function torol() {
    if (!(await confirm("Törlöd a feltöltött kimenő számlát?"))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/finance/revenues/${revenueId}/szamla`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <StopClickPropagation>
      <span className="flex items-center justify-end gap-1.5">
        {url ? (
          <a href={url} target="_blank" rel="noopener noreferrer" className="max-w-[140px] truncate text-text-accent hover:underline">
            {filename ?? "Számla"}
          </a>
        ) : (
          <span className="text-text-muted">–</span>
        )}
        {canEdit && (
          <>
            <input
              ref={inputRef}
              type="file"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void feltolt(file);
                e.target.value = "";
              }}
            />
            <button
              type="button"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
              title={url ? "Másik fájl feltöltése" : "Számla feltöltése"}
              className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-primary disabled:opacity-50"
            >
              <Upload size={13} />
            </button>
          </>
        )}
        {url && canDelete && (
          <button
            type="button"
            disabled={busy}
            onClick={torol}
            title="Feltöltött számla törlése"
            className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
          >
            <Trash2 size={13} />
          </button>
        )}
      </span>
    </StopClickPropagation>
  );
}
