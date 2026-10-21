"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";
import type { EmployeeDocument } from "@/lib/api";

/** A munkatárshoz feltöltött dokumentumok (pl. munkaszerződés) listája -
 * tetszőleges számú fájl feltölthető, mindegyik saját sorban, névvel és
 * külön törlés-gombbal (lásd backend crew.py munkaszerzodesek végpontjai). */
export function MunkaszerzodesUpload({ employeeId, documents }: { employeeId: number; documents: EmployeeDocument[] }) {
  const router = useRouter();
  const confirm = useConfirm();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await authFetch(`/api/v1/crew/${employeeId}/munkaszerzodesek`, { method: "POST", body: fd });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen feltöltés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen feltöltés (hálózati hiba): ${err}`);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function handleDelete(doc: EmployeeDocument) {
    if (!(await confirm(`Törlöd a(z) "${doc.filename}" fájlt?`))) return;
    setDeletingId(doc.id);
    try {
      const res = await authFetch(`/api/v1/crew/${employeeId}/munkaszerzodesek/${doc.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-2">
      {documents.length === 0 ? (
        <p className="text-[13px] text-text-muted">Nincs feltöltött munkaszerződés.</p>
      ) : (
        <ul className="space-y-1.5">
          {documents.map((doc) => (
            <li key={doc.id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
              <a href={doc.url} target="_blank" rel="noopener noreferrer" className="text-text-accent hover:underline">
                {doc.filename}
              </a>
              <button
                type="button"
                onClick={() => handleDelete(doc)}
                disabled={deletingId === doc.id}
                className="rounded-[var(--radius)] border border-border px-2 py-0.5 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {deletingId === doc.id ? "Törlés…" : "Törlés"}
              </button>
            </li>
          ))}
        </ul>
      )}
      <label className="inline-block cursor-pointer rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3">
        {uploading ? "Feltöltés…" : "+ Fájl feltöltése"}
        <input ref={inputRef} type="file" className="hidden" disabled={uploading} onChange={handleFileChange} />
      </label>
    </div>
  );
}
