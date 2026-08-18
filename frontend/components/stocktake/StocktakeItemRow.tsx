"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { StocktakeItem } from "@/lib/api";
import { SelectDropdown } from "@/components/SelectDropdown";

/** Azok az állapotok, amikhez MAGYARÁZAT is kell, mielőtt a leltár lezárható -
 * a backend ugyanezt kényszeríti ki (services/stocktake.py
 * MAGYARAZATOT_IGENYLO_STATUSZOK), itt csak azért ismételjük meg, hogy a mező
 * ott jelenjen meg, ahol kell, és ne a lezárásnál derüljön ki. */
const MAGYARAZATOT_IGENYLO_ALLAPOTOK = ["Szerelendő", "Szervíz"];

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

  async function save(payload: { status?: string | null; counted_qty?: number | null; megjegyzes?: string | null }) {
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

  const magyarazatKell = item.status !== null && MAGYARAZATOT_IGENYLO_ALLAPOTOK.includes(item.status);
  const magyarazatHianyzik = magyarazatKell && !(item.megjegyzes ?? "").trim();
  // A darabszám-eltérés (több VAGY kevesebb) itt is látszik, ne csak az
  // összesítésben: aki most számolta meg, az tudja a legjobban, mi történt.
  const elteres =
    item.expected_qty !== null && item.counted_qty !== null ? item.counted_qty - item.expected_qty : null;

  return (
    <div className="flex flex-col gap-1.5 border-b border-border px-3 py-2 last:border-b-0">
      <div className="flex items-center justify-between gap-3">
        <a
          href={`/felszereles/${item.equipment_id}`}
          className="min-w-0 flex-1 truncate text-[13px] text-text-primary hover:underline"
        >
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
              {elteres !== null && elteres !== 0 && (
                <span className={elteres > 0 ? "text-text-warning" : "text-text-danger"}>
                  {elteres > 0 ? `+${elteres} többlet` : `${elteres} hiány`}
                </span>
              )}
            </div>
          )}
          {item.track_mode !== "stock" && (
            <SelectDropdown
              disabled={busy}
              value={item.status ?? null}
              options={allapotOptions}
              onChange={(next) => save({ status: next })}
              placeholder="Nincs beállítva"
              className="min-w-[160px]"
            />
          )}
        </div>
      </div>

      {/* Szerelendő / szervizes eszköznél a MIÉRT is kell: egy hónappal később
          a puszta állapotból már senki nem tudja, mi a baja és hol van. Amíg
          üres, a leltárt a backend nem engedi lezárni. */}
      {magyarazatKell && (
        <div className="flex flex-col gap-1">
          <textarea
            rows={2}
            disabled={busy}
            defaultValue={item.megjegyzes ?? ""}
            placeholder="Miért szerelendő / miért van szervizben? (mi a baja, hol van, ki vitte el)"
            onBlur={(e) => {
              const value = e.target.value;
              if (value !== (item.megjegyzes ?? "")) save({ megjegyzes: value });
            }}
            className={`w-full rounded-[var(--radius)] border bg-surface-2 px-2 py-1.5 text-[13px] leading-relaxed text-text-primary focus:outline-none ${
              magyarazatHianyzik ? "border-[color:var(--text-danger)]" : "border-border"
            }`}
          />
          {magyarazatHianyzik && (
            <p className="text-[12px] text-text-danger">Enélkül a leltározás nem zárható le.</p>
          )}
        </div>
      )}
    </div>
  );
}
