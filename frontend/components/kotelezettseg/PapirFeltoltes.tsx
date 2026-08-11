"use client";

import { useCallback, useEffect, useState } from "react";
import { Paperclip, Trash2, Upload } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";
import type { DocumentAttachment } from "@/lib/api";

/** Egy rekordhoz feltöltött papírok (számla, kötvény, blokk, bármi).
 *
 * A meglévő DokumentumFeltoltes komponenstől abban tér el, hogy a listát MAGA
 * kéri le: ezek a blokkok lenyitáskor jelennek meg, és a szülő oldal több
 * tucat sort renderel - ha mindegyikhez előre le kellene kérni a
 * csatolmányokat, az oldal megnyitása indítana több tucat kérést olyan
 * sorokhoz, amiket a felhasználó ki sem nyit. */
export function PapirFeltoltes({
  entityType,
  entityId,
  kategoria = "egyeb",
  canEdit,
  canDelete,
  uresSzoveg = "Nincs feltöltött dokumentum.",
}: {
  entityType: string;
  entityId: number;
  kategoria?: string;
  canEdit: boolean;
  canDelete: boolean;
  uresSzoveg?: string;
}) {
  const confirm = useConfirm();
  const [fajlok, setFajlok] = useState<DocumentAttachment[] | null>(null);
  const [busy, setBusy] = useState(false);

  const betolt = useCallback(async () => {
    const res = await authFetch(`/api/v1/csatolmanyok/${entityType}/${entityId}`);
    if (!res.ok) {
      setFajlok([]);
      return;
    }
    setFajlok((await res.json()) as DocumentAttachment[]);
  }, [entityType, entityId]);

  useEffect(() => {
    betolt();
  }, [betolt]);

  async function feltolt(input: HTMLInputElement, files: File[]) {
    setBusy(true);
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append("file", file);
        const res = await authFetch(`/api/v1/csatolmanyok/${entityType}/${entityId}?kategoria=${kategoria}`, {
          method: "POST",
          body: fd,
        });
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          alert(`Sikertelen feltöltés (${file.name}): ${detail?.detail ?? res.status}`);
          break;
        }
      }
      await betolt();
    } finally {
      setBusy(false);
      input.value = "";
    }
  }

  async function torol(fajl: DocumentAttachment) {
    if (!(await confirm(`Törlöd ezt a fájlt: "${fajl.filename}"?`))) return;
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${fajl.id}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      await betolt();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-1.5">
      {fajlok === null ? (
        <p className="text-[12px] text-text-muted">Betöltés…</p>
      ) : fajlok.length === 0 ? (
        <p className="text-[12px] text-text-muted">{uresSzoveg}</p>
      ) : (
        <ul className="space-y-1">
          {fajlok.map((f) => (
            <li key={f.id} className="flex items-center gap-2 text-[12.5px]">
              <Paperclip size={12} className="shrink-0 text-text-muted" />
              <a
                href={f.url}
                target="_blank"
                rel="noopener noreferrer"
                className="max-w-[280px] truncate text-text-accent hover:underline"
                title={f.filename}
              >
                {f.filename}
              </a>
              {canDelete && (
                <button
                  type="button"
                  onClick={() => torol(f)}
                  disabled={busy}
                  title="Fájl törlése"
                  className="rounded-[var(--radius)] p-0.5 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        // GOMB, nem link-stílusú szöveg: a korábbi, aláhúzott-kék változatot
        // több felhasználó URL-beírásnak olvasta, pedig a gépről tölt fel
        // fájlt. A címke is kimondja, mit vár (PDF vagy fotó).
        <label
          className={`inline-flex w-fit items-center gap-1.5 rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary ${
            busy ? "opacity-50" : "cursor-pointer hover:bg-surface-3"
          }`}
        >
          <Upload size={12} />
          {busy ? "Feltöltés…" : "Fájl feltöltése a gépről (PDF, fotó)"}
          <input
            type="file"
            multiple
            // A telefon így a kamerát és a galériát is felajánlja, a gépen
            // pedig eleve a fájlválasztó nyílik - a lista csak szűkítés, nem
            // korlátozás (az "egyéb papír" bármi lehet).
            accept="application/pdf,image/*"
            disabled={busy}
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              if (files.length > 0) feltolt(e.target, files);
            }}
            className="hidden"
          />
        </label>
      )}
    </div>
  );
}
