"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { MessageSquare, Pencil, Trash2 } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { KommentChat } from "@/components/KommentChat";
import { SearchableIdPicker } from "@/components/SearchableIdPicker";
import type { AutoTeendo } from "@/lib/api";

const inputClass =
  "rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

/** Egy teendő átírása helyben: szöveg, határidő, felelős - a pipát a sor
 * checkboxa kezeli, azt itt nem ismételjük meg. */
function TeendoSzerkeszto({
  autoId,
  teendo,
  emberek,
  onKesz,
}: {
  autoId: number;
  teendo: AutoTeendo;
  emberek: { id: number; full_name: string }[];
  onKesz: () => void;
}) {
  const router = useRouter();
  const [szoveg, setSzoveg] = useState(teendo.szoveg);
  const [hatarido, setHatarido] = useState(teendo.hatarido ?? "");
  const [felelosId, setFelelosId] = useState<number | null>(teendo.felelos_id);
  const [busy, setBusy] = useState(false);

  async function ment() {
    if (!szoveg.trim()) {
      alert("A teendő szövege nem lehet üres.");
      return;
    }
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/autok/${autoId}/teendok/${teendo.id}`, {
        method: "PATCH",
        body: JSON.stringify({ szoveg: szoveg.trim(), hatarido: hatarido || null, felelos_id: felelosId }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      onKesz();
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fade-in flex flex-wrap items-center gap-2">
      <input
        value={szoveg}
        onChange={(e) => setSzoveg(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void ment();
          }
        }}
        disabled={busy}
        aria-label="Teendő szövege"
        className={`${inputClass} min-w-[220px] flex-1`}
      />
      <input
        type="date"
        value={hatarido}
        onChange={(e) => setHatarido(e.target.value)}
        disabled={busy}
        aria-label="Határidő"
        className={inputClass}
      />
      <SearchableIdPicker
        value={felelosId}
        options={emberek.map((e) => ({ id: e.id, label: e.full_name }))}
        onChange={setFelelosId}
        placeholder="Felelős (opcionális)…"
        disabled={busy}
        className="min-w-[180px]"
      />
      <button
        type="button"
        disabled={busy || !szoveg.trim()}
        onClick={() => void ment()}
        className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
      >
        Mentés
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={onKesz}
        className="rounded-[var(--radius)] px-2 py-1.5 text-[13px] text-text-muted hover:bg-surface-3"
      >
        Mégse
      </button>
    </div>
  );
}

/** Teendők egy autóhoz - pipálható lista ("vinni műszakira", "izzót
 * cserélni"), opcionális határidővel és felelőssel; minden teendő átírható
 * és kommentelhető is (lásd backend routes/autok.py "teendok" végpontjai). */
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
  const [szerkesztett, setSzerkesztett] = useState<number | null>(null);
  const [nyitottChat, setNyitottChat] = useState<number | null>(null);

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
          <div key={t.id}>
            {szerkesztett === t.id ? (
              <TeendoSzerkeszto autoId={autoId} teendo={t} emberek={emberek} onKesz={() => setSzerkesztett(null)} />
            ) : (
              <div className="flex flex-wrap items-center gap-2 text-[13px]">
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
                {canEdit && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => setSzerkesztett(t.id)}
                    title="Teendő szerkesztése"
                    className="rounded-[var(--radius)] p-0.5 text-text-muted hover:text-text-primary disabled:opacity-50"
                  >
                    <Pencil size={12} />
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setNyitottChat(nyitottChat === t.id ? null : t.id)}
                  title={nyitottChat === t.id ? "Hozzászólások elrejtése" : "Hozzászólások"}
                  className={`flex items-center gap-1 rounded-[var(--radius)] p-0.5 text-[12px] ${
                    nyitottChat === t.id ? "text-text-accent" : "text-text-muted hover:text-text-primary"
                  }`}
                >
                  <MessageSquare size={12} />
                  {t.kommentek.length > 0 && <span>{t.kommentek.length}</span>}
                </button>
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
            )}
            {nyitottChat === t.id && (
              <div className="fade-in mt-2 ml-6 max-w-xl rounded-[var(--radius)] border border-border bg-surface-2 p-3">
                <KommentChat
                  endpoint={`/api/v1/autok/${autoId}/teendok/${t.id}/kommentek`}
                  topic={`autoTeendoComments:${t.id}`}
                  initialComments={t.kommentek}
                  mentionableEmployees={emberek}
                />
              </div>
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
