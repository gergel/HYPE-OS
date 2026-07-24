"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";

/** Egy rekord törlésére szolgáló gomb - a `path` a teljes DELETE végpont
 * (pl. /api/v1/deliverables/42). Bejelentkezés (admin/operátor szerepkör)
 * szükséges hozzá, a token a localStorage-ból megy a kérésbe. Lista-sorban
 * (redirectTo nélkül) törlés után egyszerűen frissül az oldal; egy
 * részletnézeten (redirectTo megadva) a törölt rekord saját oldala már nem
 * létezik, ezért oda kell navigálni egy listára törlés után. */
export function DeleteButton({
  path,
  onDeleted,
  redirectTo,
  label,
  className,
}: {
  path: string;
  onDeleted?: () => void;
  redirectTo?: string;
  label?: string;
  className?: string;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (!(await confirm("Biztosan törlöd ezt a rekordot?"))) return;
    setBusy(true);
    try {
      const res = await authFetch(path, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Törlés sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      onDeleted?.();
      if (redirectTo) {
        router.push(redirectTo);
      } else {
        router.refresh();
      }
    } catch (err) {
      alert(`Törlés sikertelen: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className={className ?? "text-text-muted hover:text-text-danger disabled:opacity-50"}
      title="Törlés"
    >
      {label ?? "✕"}
    </button>
  );
}
