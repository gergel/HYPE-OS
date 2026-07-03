"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type Result = { status: string; message: string; technika_lista: string | null };

/** A "Technika ready" gomb - lefuttatja a napi bontású ütközés-ellenőrzést a
 * projekthez rendelt eszközökre (a HYPE_Technika Railway program portolt logikája),
 * és megjeleníti az eredményt (OK/ISSUE + üzenet). */
export function TechnikaCheckButton({ projectId }: { projectId: number }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  async function handleClick() {
    setBusy(true);
    setResult(null);
    try {
      const res = await authFetch(`/api/v1/projects/${projectId}/technika-check`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      const data: Result = await res.json();
      setResult(data);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={handleClick}
        disabled={busy}
        className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        {busy ? "Ellenőrzés…" : "Technika ready - eszközök ellenőrzése"}
      </button>
      {result && (
        <div
          className={`mt-3 whitespace-pre-line rounded-[var(--radius)] border p-3 text-[13px] ${
            result.status === "OK" ? "border-text-success text-text-success" : "border-text-danger text-text-danger"
          }`}
        >
          <strong>{result.status === "OK" ? "Nincs ütközés." : "Ütközés!"}</strong>
          {result.message && result.message !== "OK" && <div className="mt-1">{result.message}</div>}
        </div>
      )}
    </div>
  );
}
