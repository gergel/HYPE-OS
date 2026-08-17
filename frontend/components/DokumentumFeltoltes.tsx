"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Paperclip, Trash2 } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";
import type { DocumentAttachment } from "@/lib/api";

const KATEGORIA_NEVEK: Record<string, string> = {
  szerzodes: "Szerződés",
  tig: "TIG",
  szamla: "Számla",
  diszpo: "Diszpóhoz",
  gyartas: "Gyártáshoz",
  egyeb: "Egyéb",
};

function meret(bajt: number | null): string {
  if (!bajt) return "";
  if (bajt < 1024 * 1024) return `${Math.round(bajt / 1024)} kB`;
  return `${(bajt / 1024 / 1024).toFixed(1)} MB`;
}

/** Egy rekordhoz (szerződéshez, projektkódhoz, kiadáshoz…) tartozó fájlok:
 * feltöltés, megnyitás, törlés. A fájl mindig az R2 tárhelyre kerül, nem a
 * szolgáltatás lemezére - lásd backend services/attachments.py.
 *
 * A `kategoria` mondja meg, mi ez a fájl (szerződés / TIG / számla): a havi
 * számla-csomag (Pénzügyek oldal) ez alapján találja meg a számlákat. */
export function DokumentumFeltoltes({
  entityType,
  entityId,
  attachments,
  kategoria = "egyeb",
  canEdit,
  canDelete,
  emptyText = "Nincs feltöltött fájl.",
}: {
  entityType: string;
  entityId: number;
  attachments: DocumentAttachment[];
  kategoria?: DocumentAttachment["kategoria"];
  canEdit: boolean;
  canDelete: boolean;
  emptyText?: string;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  /** Egyszerre több fájl is kiválasztható. EGYENKÉNT, sorban töltjük fel:
   * így egy hibás fájl (pl. túl nagy) csak magát bukja, a többi felmegy - és
   * a felhasználó látja, melyiknél akadt el. */
  async function feltolt(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    const hibak: string[] = [];
    try {
      for (const file of files) {
        setUploading(file.name);
        try {
          const fd = new FormData();
          fd.append("file", file);
          const res = await authFetch(
            `/api/v1/csatolmanyok/${entityType}/${entityId}?kategoria=${encodeURIComponent(kategoria)}`,
            { method: "POST", body: fd },
          );
          if (!res.ok) {
            const detail = await res.json().catch(() => null);
            hibak.push(`${file.name}: ${detail?.detail ?? res.status}`);
          }
        } catch (err) {
          hibak.push(`${file.name}: ${err}`);
        }
      }
      if (hibak.length > 0) alert(`Sikertelen feltöltés:\n${hibak.join("\n")}`);
      router.refresh();
    } finally {
      setUploading(null);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function torol(doc: DocumentAttachment) {
    if (!(await confirm(`Törlöd a(z) "${doc.filename}" fájlt?`))) return;
    setDeletingId(doc.id);
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${doc.id}`, { method: "DELETE" });
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
      {attachments.length === 0 ? (
        <p className="text-[13px] text-text-muted">{emptyText}</p>
      ) : (
        <ul className="space-y-1.5">
          {attachments.map((doc) => (
            <li key={doc.id} className="flex flex-wrap items-center justify-between gap-2 text-[13px]">
              <span className="flex min-w-0 items-center gap-1.5">
                <Paperclip size={13} className="shrink-0 text-text-muted" />
                <a
                  href={doc.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="truncate text-text-accent hover:underline"
                >
                  {doc.filename}
                </a>
                <span className="shrink-0 text-[12px] text-text-muted">
                  {KATEGORIA_NEVEK[doc.kategoria] ?? doc.kategoria}
                  {doc.meret_bajt ? ` · ${meret(doc.meret_bajt)}` : ""}
                </span>
              </span>
              {canDelete && (
                <button
                  type="button"
                  onClick={() => torol(doc)}
                  disabled={deletingId === doc.id}
                  title="Fájl törlése"
                  className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                >
                  <Trash2 size={13} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <label className="inline-block cursor-pointer rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3">
          {uploading ? `Feltöltés… (${uploading})` : "+ Fájlok feltöltése"}
          <input ref={inputRef} type="file" multiple className="hidden" disabled={!!uploading} onChange={feltolt} />
        </label>
      )}
    </div>
  );
}
