"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { selectColor } from "@/lib/selectColor";
import type { StocktakeItem } from "@/lib/api";

/** Egy eszköz sora a leltározás oldalon - az állapotát (színes select) a
 * "stock" track_mode-ú eszközök KIVÉTELÉVEL mindenki kaphat (a track_mode
 * Notion-import-eredetű besorolás, sokszor pontatlan, ezért a darabszám-mező
 * megjelenítését nem erre, hanem arra alapozzuk, hogy van-e ténylegesen elvárt
 * mennyiség beállítva - lásd services/stocktake.py start_session). Minden
 * változtatás azonnal ment - a szerkesztő oldal lezárt leltározásnál átirányít
 * az eredményoldalra, ide (élő szerkesztésre) így csak nyitott leltározásnál
 * lehet eljutni. */
export function StocktakeItemRow({
  sessionId,
  item,
  allapotOptions,
}: {
  sessionId: number;
  item: StocktakeItem;
  allapotOptions: string[];
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function save(payload: { status?: string | null; counted_qty?: number | null }) {
    setBusy(true);
    try {
      const res = await authFetch(`/api/v1/stocktake/sessions/${sessionId}/items/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
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
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2 last:border-b-0">
      <a href={`/felszereles/${item.equipment_id}`} className="min-w-0 flex-1 truncate text-[13px] text-text-primary hover:underline">
        {item.equipment_nev}
      </a>
      <div className="flex items-center gap-3">
        {item.expected_qty !== null && (
          <div className="flex items-center gap-2 text-[13px] text-text-secondary">
            <span className="text-text-muted">Elvárt: {item.expected_qty}</span>
            <input
              type="number"
              disabled={busy}
              defaultValue={item.counted_qty ?? ""}
              placeholder="Megszámolt"
              onBlur={(e) => {
                const value = e.target.value === "" ? null : Number(e.target.value);
                if (value !== item.counted_qty) save({ counted_qty: value });
              }}
              className="w-24 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
            />
          </div>
        )}
        {item.track_mode !== "stock" && (
          <select
            disabled={busy}
            value={item.status ?? ""}
            onChange={(e) => save({ status: e.target.value || null })}
            className="rounded-[var(--radius)] border border-border px-2 py-1 text-[13px] focus:outline-none"
            style={item.status ? { background: selectColor(item.status).bg, color: selectColor(item.status).text } : undefined}
          >
            <option value="">Nincs beállítva</option>
            {allapotOptions.map((opt) => (
              <option key={opt} value={opt} style={{ background: selectColor(opt).bg, color: selectColor(opt).text }}>
                {opt}
              </option>
            ))}
          </select>
        )}
      </div>
    </div>
  );
}
