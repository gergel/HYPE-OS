"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { StatusBadge } from "@/components/StatusBadge";
import type { Contract } from "@/lib/api";

/** Megrendelői szerződés kezelése egy Project Code-hoz - ha a megrendelőnek
 * már van keretszerződése (lásd backend client_contracts.py
 * existing_keretszerzodes_id), egy kattintással újrafelhasználható, ha
 * nincs, egy új (erre a Project Code-ra szóló) szerződést kell felvinni.
 * Miután van kapcsolt szerződés, ide tölthető fel a (aláírt) dokumentum. */
export function ClientContractManager({
  projectCodeId,
  existingContract,
  existingKeretszerzodesId,
}: {
  projectCodeId: number;
  existingContract: Contract | null;
  existingKeretszerzodesId: number | null;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ ceg_neve: "", szekhely: "", adoszam: "", megbizas_targya: "" });
  const inputRef = useRef<HTMLInputElement>(null);

  async function useExisting() {
    if (!existingKeretszerzodesId) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/megrendeloi-szerzodesek/${projectCodeId}/use-existing/${existingKeretszerzodesId}`, {
        method: "POST",
      });
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

  async function createNew() {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/megrendeloi-szerzodesek/${projectCodeId}/create`, {
        method: "POST",
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      setCreating(false);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function uploadFile(file: File) {
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await authFetch(`/api/v1/megrendeloi-szerzodesek/${projectCodeId}/fajl`, { method: "POST", body: fd });
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

  if (existingContract) {
    return (
      <div className="space-y-2 text-[13px]">
        <div className="flex items-center gap-2">
          <span className="text-text-secondary">Állapot:</span>
          <StatusBadge
            label={existingContract.szerzodes_allapota ?? "Készítés alatt"}
            tone={existingContract.szerzodes_allapota === "Kiküldve" ? "success" : "warning"}
          />
        </div>
        {existingContract.szerzodes_file_url ? (
          <a href={existingContract.szerzodes_file_url} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
            Szerződés megnyitása
          </a>
        ) : (
          <label className="inline-block cursor-pointer rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-secondary hover:bg-surface-3">
            {busy ? "Feltöltés…" : "+ Aláírt szerződés feltöltése"}
            <input
              ref={inputRef}
              type="file"
              className="hidden"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadFile(file);
              }}
            />
          </label>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3 text-[13px]">
      {existingKeretszerzodesId ? (
        <div>
          <p className="mb-2 text-text-secondary">A megrendelőnek már van álló keretszerződése - ez a Project Code is ahhoz köthető.</p>
          <button
            type="button"
            onClick={useExisting}
            disabled={busy}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Mentés…" : "Meglévő keretszerződés használata"}
          </button>
        </div>
      ) : (
        <p className="text-text-secondary">A megrendelőnek nincs álló keretszerződése - eseti szerződés szükséges ehhez a Project Code-hoz.</p>
      )}
      {!creating ? (
        <button
          type="button"
          onClick={() => setCreating(true)}
          disabled={busy}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          + Új (eseti) szerződés felvitele
        </button>
      ) : (
        <div className="space-y-2 rounded-[var(--radius)] border border-border p-3">
          <input
            placeholder="Cég neve"
            value={form.ceg_neve}
            onChange={(e) => setForm((f) => ({ ...f, ceg_neve: e.target.value }))}
            className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-text-primary focus:outline-none"
          />
          <input
            placeholder="Székhely"
            value={form.szekhely}
            onChange={(e) => setForm((f) => ({ ...f, szekhely: e.target.value }))}
            className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-text-primary focus:outline-none"
          />
          <input
            placeholder="Adószám"
            value={form.adoszam}
            onChange={(e) => setForm((f) => ({ ...f, adoszam: e.target.value }))}
            className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-text-primary focus:outline-none"
          />
          <input
            placeholder="Megbízás tárgya"
            value={form.megbizas_targya}
            onChange={(e) => setForm((f) => ({ ...f, megbizas_targya: e.target.value }))}
            className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-text-primary focus:outline-none"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setCreating(false)}
              disabled={busy}
              className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-text-secondary hover:bg-surface-3 disabled:opacity-50"
            >
              Mégse
            </button>
            <button
              type="button"
              onClick={createNew}
              disabled={busy}
              className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-text-accent hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Mentés…" : "Létrehozás"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
