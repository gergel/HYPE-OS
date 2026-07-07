"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

/** A munkatárs munkaszerződésének feltöltése (PDF/Word/kép) - a korábbi sima
 * URL-szöveg mező helyett, mert egy fájlt kell tudni csatolni, nem linket
 * beírni. Minden feltöltés felülírja az előzőt (lásd backend crew.py
 * upload_munkaszerzodes - ugyanaz az R2 kulcs, employee_id alapján). */
export function MunkaszerzodesUpload({ employeeId, currentUrl }: { employeeId: number; currentUrl: string | null }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await authFetch(`/api/v1/crew/${employeeId}/munkaszerzodes`, { method: "POST", body: fd });
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
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      {currentUrl ? (
        <a href={currentUrl} target="_blank" rel="noopener noreferrer" className="text-[13px] text-text-accent hover:underline">
          Csatolt fájl megnyitása
        </a>
      ) : (
        <span className="text-[13px] text-text-muted">Nincs feltöltött munkaszerződés.</span>
      )}
      <label className="cursor-pointer rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3">
        {busy ? "Feltöltés…" : currentUrl ? "Csere" : "Feltöltés"}
        <input ref={inputRef} type="file" className="hidden" disabled={busy} onChange={handleFileChange} />
      </label>
    </div>
  );
}
