"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { SearchableIdPicker } from "@/components/SearchableIdPicker";
import type { AutoTeendo } from "@/lib/api";

const inputClass =
  "rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

/** Teendők egy autóhoz - pipálható lista ("vinni műszakira", "izzót
 * cserélni"), opcionális határidővel és felelőssel (a felhasználó kérése,
 * lásd backend routes/autok.py "teendok" végpontjai). */
export function AutoTeendok({
  autoId,
  teendok,
  emberek,
  canEdit,
  canDelete,
}: {
  autoId: number;
  teendok: AutoTeendo[];
  emberek: { id: number; full_name: string }[];
  canEdit: boolean;
  canDelete: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [ujSzoveg, setUjSzoveg] = useState("");
  const [ujHatarido, setUjHatarido] = useState("");
  const [ujFelelos, setUjFelelos] = useState<number | null>(null);

  async function keres(url: string, init: RequestInit) {
    setBusy(true);
    try {
      const res = await authFetch(url, init);
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return false;
      }
      router.refresh();
      return true;
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function hozzaad() {
    const szoveg = ujSzoveg.trim();
    if (!szoveg) return;
    const ok = await keres(`/api/v1/autok/${autoId}/teendok`, {
      method: "POST",
      body: JSON.stringify({ szoveg, hatarido: ujHatarido || null, felelos_id: ujFelelos }),
    });
    if (ok) {
      setUjSzoveg("");
      setUjHatarido("");
      setUjFelelos(null);
    }
  }

  return (
    <div>
      {teendok.length === 0 && <p className="text-[12.5px] text-text-muted">Nincs felvezetve teendő ehhez az autóhoz.</p>}
      <div className="space-y-1.5">
        {teendok.map((t) => (
          <div key={t.id} className="flex flex-wrap items-center gap-2 text-[13px]">
            <input
              type="checkbox"
              checked={t.kesz}
              disabled={!canEdit || busy}
              onChange={(e) =>
                void keres(`/api/v1/autok/${autoId}/teendok/${t.id}`, {
                  method: "PATCH",
                  body: JSON.stringify({ kesz: e.target.checked }),
                })
              }
              className="cursor-pointer"
              aria-label={`${t.szoveg} kész`}
            />
            <span className={t.kesz ? "text-text-muted line-through" : "text-text-primary"}>{t.szoveg}</span>
            {t.hatarido && <span className="text-[12px] text-text-muted">– {t.hatarido}</span>}
            {t.felelos_nev && <span className="text-[12px] text-text-muted">({t.felelos_nev})</span>}
            {canDelete && (
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  void keres(`/api/v1/autok/${autoId}/teendok/${t.id}`, { method: "DELETE" })
                }
                title="Teendő törlése"
                className="rounded-[var(--radius)] p-0.5 text-text-muted hover:text-text-danger disabled:opacity-50"
              >
                <Trash2 size={12} />
              </button>
            )}
          </div>
        ))}
      </div>

      {canEdit && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            value={ujSzoveg}
            onChange={(e) => setUjSzoveg(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void hozzaad();
              }
            }}
            placeholder="Új teendő (pl. vinni műszakira)…"
            disabled={busy}
            className={`${inputClass} min-w-[220px] flex-1`}
          />
          <input
            type="date"
            value={ujHatarido}
            onChange={(e) => setUjHatarido(e.target.value)}
            disabled={busy}
            aria-label="Határidő"
            className={inputClass}
          />
          <SearchableIdPicker
            value={ujFelelos}
            options={emberek.map((e) => ({ id: e.id, label: e.full_name }))}
            onChange={setUjFelelos}
            placeholder="Felelős (opcionális)…"
            disabled={busy}
            className="min-w-[180px]"
          />
          <button
            type="button"
            disabled={busy || !ujSzoveg.trim()}
            onClick={() => void hozzaad()}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            + Hozzáadás
          </button>
        </div>
      )}
    </div>
  );
}
