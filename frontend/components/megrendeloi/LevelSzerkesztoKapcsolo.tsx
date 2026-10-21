"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/authFetch";

/** A KIMENŐ LEVÉL ÁTÍRÁSA (a felhasználó kérése): egy kapcsolóval
 * bekapcsolható; bekapcsolva megjelenik a tárgy és a szöveg az alap levéllel
 * kitöltve, és átírható. Ha nem írják át (vagy kikapcsolják), az alap levél
 * megy - a hívó űrlapjában az üres `targy` / `szoveg` ezt jelenti.
 *
 * Az alap levelet a szerver adja (az előnézet végpontja, PDF nélkül), mert a
 * projekt nevétől függ - lásd backend megrendeloi_papirok._kimeno. */
export function LevelSzerkesztoKapcsolo({
  fajta,
  projectCodeId,
  projektNev,
  targy,
  szoveg,
  onChange,
  disabled,
}: {
  fajta: string;
  projectCodeId: number;
  projektNev: string;
  targy: string;
  szoveg: string;
  onChange: (v: { targy?: string; szoveg?: string }) => void;
  disabled?: boolean;
}) {
  // Ha a papíron már van átírt levél, nyitva indul.
  const [be, setBe] = useState(() => !!(targy.trim() || szoveg.trim()));
  const [alap, setAlap] = useState<{ targy: string; szoveg: string } | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  useEffect(() => {
    if (!be) return;
    let ervenyes = true;
    const idozito = setTimeout(() => {
      authFetch(`/api/v1/megrendeloi-papirok/${fajta}/${projectCodeId}/elonezet?pdf=false`, {
        method: "POST",
        body: JSON.stringify({ projekt_nev: projektNev || null }),
      })
        .then(async (res) => {
          const d = await res.json().catch(() => null);
          if (!res.ok) throw new Error(typeof d?.detail === "string" ? d.detail : `HTTP ${res.status}`);
          if (!ervenyes) return;
          setAlap({ targy: d.alap_targy ?? "", szoveg: d.alap_szoveg ?? "" });
          setHiba(null);
        })
        .catch((err) => ervenyes && setHiba(String(err instanceof Error ? err.message : err)));
    }, 300);
    return () => {
      ervenyes = false;
      clearTimeout(idozito);
    };
  }, [be, fajta, projectCodeId, projektNev]);

  function valt(uj: boolean) {
    setBe(uj);
    // Kikapcsolva vissza az alap levélre.
    if (!uj) onChange({ targy: "", szoveg: "" });
  }

  const atirva = !!(targy.trim() || szoveg.trim());
  const mezo =
    "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

  return (
    <div className="mt-4 rounded-[var(--radius)] border border-border bg-surface-1 p-3">
      <label className="flex cursor-pointer items-center gap-2 text-[13px] text-text-primary">
        <input
          type="checkbox"
          role="switch"
          aria-checked={be}
          checked={be}
          onChange={(e) => valt(e.target.checked)}
          disabled={disabled}
        />
        E-mail szövegének szerkesztése
        <span className="text-[12px] text-text-muted">
          {be ? (atirva ? "– átírt levél megy ki" : "– még az alap levél") : "– kikapcsolva az alap levél megy ki"}
        </span>
      </label>
      {be && (
        <div className="mt-3 space-y-2">
          {hiba && <p className="text-[12px] text-text-danger">Az alap levél nem töltődött be: {hiba}</p>}
          {!alap && !hiba ? (
            <p className="text-[12px] text-text-muted">Az alap levél betöltése…</p>
          ) : (
            <>
              <label className="flex flex-col gap-1 text-[11px] text-text-muted">
                E-mail tárgya
                <input
                  value={targy || alap?.targy || ""}
                  onChange={(e) => onChange({ targy: e.target.value === alap?.targy ? "" : e.target.value })}
                  disabled={disabled}
                  className={mezo}
                />
              </label>
              <label className="flex flex-col gap-1 text-[11px] text-text-muted">
                A levél szövege
                <textarea
                  value={szoveg || alap?.szoveg || ""}
                  onChange={(e) =>
                    onChange({ szoveg: e.target.value.trim() === (alap?.szoveg ?? "").trim() ? "" : e.target.value })
                  }
                  rows={7}
                  disabled={disabled}
                  className={mezo}
                />
              </label>
              {atirva && (
                <button
                  type="button"
                  onClick={() => onChange({ targy: "", szoveg: "" })}
                  disabled={disabled}
                  className="text-[12px] text-text-accent hover:underline"
                >
                  Vissza az alap levélre
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
