"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Paperclip, Trash2 } from "lucide-react";
import { useAlertDialog, useConfirm } from "@/components/ConfirmProvider";
import { StatusBadge } from "@/components/StatusBadge";
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

/** A számla fizetési állapota egyetlen jelzőben - a határidő és a
 * kifizetés-dátum együtt mondja meg, hol tart. */
function fizetesiJelzo(doc: DocumentAttachment): { label: string; tone: "success" | "warning" | "danger" } | null {
  if (doc.kifizetve_datuma) return { label: `Kifizetve · ${doc.kifizetve_datuma}`, tone: "success" };
  if (doc.fizetesi_hatarido) {
    // Szöveges (nem Date-objektumos) összehasonlítás: az ISO "ÉÉÉÉ-HH-NN" alak
    // ábécé szerint is helyesen rendeződik, és nem kell időzóna-eltolással
    // bajlódni a "ma" meghatározásához.
    const ma = new Date().toISOString().slice(0, 10);
    if (doc.fizetesi_hatarido < ma) return { label: "Lejárt határidő", tone: "danger" };
    return { label: `Határidő: ${doc.fizetesi_hatarido}`, tone: "warning" };
  }
  return null;
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
  maxOsszMeretBajt,
  meretTanacs,
  fizetesiAllapot = false,
}: {
  entityType: string;
  entityId: number;
  attachments: DocumentAttachment[];
  kategoria?: DocumentAttachment["kategoria"];
  canEdit: boolean;
  canDelete: boolean;
  emptyText?: string;
  /** Ha meg van adva, az ITT látszó fájlok EGYÜTTES mérete nem lépheti túl -
   * a diszpó mellékleteinél ez a levélbe csatolható méret (lásd backend
   * services/attachments.py DISZPO_MAX_BAJT). A böngésző előre szól, hogy ne
   * kelljen megvárni egy hosszú, úgyis elutasított feltöltést; a valódi
   * kikényszerítés a backenden van. */
  maxOsszMeretBajt?: number;
  /** Mit tegyen a felhasználó, ha nem fér bele (pl. Drive + brief-link). */
  meretTanacs?: string;
  /** SZÁMLA kategóriánál: minden feltöltött fájlhoz KÜLÖN adható meg fizetési
   * határidő és kifizetés-dátuma - egy projektkódhoz több számla is
   * tartozhat (osztott számlázás), és azok külön esedékesek/kifizetettek
   * lehetnek (lásd backend models/document_attachment.py). */
  fizetesiAllapot?: boolean;
}) {
  const router = useRouter();
  const confirm = useConfirm();
  // A méret-hibát felugró ablakban mutatjuk: több soros, és el kell olvasni
  // (mit tegyen a nagy fájllal) - egy magától eltűnő sáv kevés lenne.
  const alertDialog = useAlertDialog();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [savingId, setSavingId] = useState<number | null>(null);
  const osszesMeret = attachments.reduce((osszeg, a) => osszeg + (a.meret_bajt ?? 0), 0);

  async function mentsdAFizetesiAllapotot(
    doc: DocumentAttachment,
    valtozas: { fizetesi_hatarido?: string | null; kifizetve_datuma?: string | null },
  ) {
    setSavingId(doc.id);
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${doc.id}/fizetesi-allapot`, {
        method: "PUT",
        body: JSON.stringify({
          fizetesi_hatarido: valtozas.fizetesi_hatarido !== undefined ? valtozas.fizetesi_hatarido : doc.fizetesi_hatarido,
          kifizetve_datuma: valtozas.kifizetve_datuma !== undefined ? valtozas.kifizetve_datuma : doc.kifizetve_datuma,
        }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setSavingId(null);
    }
  }

  /** Egyszerre több fájl is kiválasztható. EGYENKÉNT, sorban töltjük fel:
   * így egy hibás fájl (pl. túl nagy) csak magát bukja, a többi felmegy - és
   * a felhasználó látja, melyiknél akadt el. */
  async function feltolt(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    const hibak: string[] = [];
    // A már fent lévők mérete a kiindulás: a korlát az EGYÜTTES méretre szól.
    let eddigiMeret = osszesMeret;
    try {
      for (const file of files) {
        if (maxOsszMeretBajt !== undefined && eddigiMeret + file.size > maxOsszMeretBajt) {
          hibak.push(
            `${file.name} (${meret(file.size)}): nem fér bele a ${meret(maxOsszMeretBajt)}-os keretbe` +
              (meretTanacs ? `.\n${meretTanacs}` : "."),
          );
          continue;
        }
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
          } else {
            eddigiMeret += file.size;
          }
        } catch (err) {
          hibak.push(`${file.name}: ${err}`);
        }
      }
      if (hibak.length > 0) await alertDialog(`Sikertelen feltöltés:\n${hibak.join("\n")}`);
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
          {attachments.map((doc) => {
            const jelzo = fizetesiAllapot ? fizetesiJelzo(doc) : null;
            return (
              <li
                key={doc.id}
                className={`rounded-[var(--radius)] text-[13px] ${
                  fizetesiAllapot ? "border border-border p-2" : ""
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
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
                    {jelzo && <StatusBadge label={jelzo.label} tone={jelzo.tone} />}
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
                </div>
                {/* EGYÉNI fizetési állapot ehhez a fájlhoz - nem a projektkód
                    egészéhez, mert egy kódhoz több számla is tartozhat, és
                    azok külön esedékesek/kifizetettek lehetnek. */}
                {fizetesiAllapot && (
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12.5px] text-text-secondary">
                    <label className="flex items-center gap-1.5">
                      Fizetési határidő:
                      <input
                        type="date"
                        value={doc.fizetesi_hatarido ?? ""}
                        disabled={!canEdit || savingId === doc.id}
                        onChange={(e) =>
                          mentsdAFizetesiAllapotot(doc, { fizetesi_hatarido: e.target.value || null })
                        }
                        className="rounded-[var(--radius)] border border-border bg-surface-3 px-1.5 py-0.5 text-[12.5px] text-text-primary disabled:opacity-50"
                      />
                    </label>
                    <label className="flex items-center gap-1.5">
                      Kifizetve:
                      <input
                        type="date"
                        value={doc.kifizetve_datuma ?? ""}
                        disabled={!canEdit || savingId === doc.id}
                        onChange={(e) =>
                          mentsdAFizetesiAllapotot(doc, { kifizetve_datuma: e.target.value || null })
                        }
                        className="rounded-[var(--radius)] border border-border bg-surface-3 px-1.5 py-0.5 text-[12.5px] text-text-primary disabled:opacity-50"
                      />
                    </label>
                    {doc.kifizetve_datuma && canEdit && (
                      <button
                        type="button"
                        onClick={() => mentsdAFizetesiAllapotot(doc, { kifizetve_datuma: null })}
                        disabled={savingId === doc.id}
                        className="text-[12px] text-text-muted hover:text-text-secondary disabled:opacity-50"
                      >
                        Kifizetés visszavonása
                      </button>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {canEdit && (
        <>
          <label className="inline-block cursor-pointer rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3">
            {uploading ? `Feltöltés… (${uploading})` : "+ Fájlok feltöltése"}
            <input ref={inputRef} type="file" multiple className="hidden" disabled={!!uploading} onChange={feltolt} />
          </label>
          {maxOsszMeretBajt !== undefined && (
            <p className="text-[12px] text-text-muted">
              Összesen {meret(maxOsszMeretBajt)} fér ide{osszesMeret > 0 ? ` (most ${meret(osszesMeret)} van fent)` : ""}.
              {meretTanacs ? ` ${meretTanacs}` : ""}
            </p>
          )}
        </>
      )}
    </div>
  );
}
