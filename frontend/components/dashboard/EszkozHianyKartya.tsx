"use client";

import { useState } from "react";
import { AlertTriangle } from "lucide-react";
import { useConfirm } from "@/components/ConfirmProvider";
import { authFetch } from "@/lib/authFetch";
import type { EszkozKivitelHiany } from "@/lib/api";

/** ESZKÖZKIVITEL-HIÁNYOK a dashboard tetején, jól láthatóan (a felhasználó
 * kérése): a lejárt kódú (a forgatás utolsó napja + 48 óra letelt), hiányos
 * kivitelek - mi hiányzik és melyik forgatásnál. Itt írható magyarázat (mi
 * lett a megoldás), és a "Kész" jelöléssel vehető le a figyelmeztetés - lásd
 * backend routes/eszkoz_kivitel.hianyok. */
export function EszkozHianyKartya({ kezdeti }: { kezdeti: EszkozKivitelHiany[] }) {
  const confirm = useConfirm();
  const [hianyok, setHianyok] = useState(kezdeti);
  const [megoldasok, setMegoldasok] = useState<Map<number, string>>(
    () => new Map(kezdeti.map((h) => [h.id, h.hiany_megoldas ?? ""])),
  );
  const [busyId, setBusyId] = useState<number | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  if (hianyok.length === 0) return null;

  async function ment(id: number, megoldva: boolean) {
    if (busyId !== null) return;
    if (megoldva) {
      const ok = await confirm(
        "Készre jelölöd ezt a hiányt? Utána már nem jelenik meg a dashboardon.",
      );
      if (!ok) return;
    }
    setBusyId(id);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/eszkozkivitelek/${id}/hiany-megoldas`, {
        method: "POST",
        body: JSON.stringify({ megoldas: megoldasok.get(id) ?? "", megoldva: megoldva || null }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? "Nem sikerült menteni.");
        return;
      }
      if (megoldva) {
        setHianyok((elozo) => elozo.filter((h) => h.id !== id));
      } else {
        const friss = await res.json();
        setHianyok((elozo) => elozo.map((h) => (h.id === id ? { ...h, hiany_megoldas: friss.hiany_megoldas } : h)));
      }
    } catch {
      setHiba("Hálózati hiba - próbáld újra.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="rounded-[var(--radius)] border border-text-danger/50 bg-surface-1 p-4 md:p-5">
      <div className="mb-3 flex items-center gap-2">
        <AlertTriangle size={18} className="text-text-danger" />
        <h2 className="text-[15px] font-semibold text-text-danger">
          Eszközkivitel: hiányos visszahozatal ({hianyok.length})
        </h2>
      </div>
      <p className="mb-4 text-[12.5px] text-text-secondary">
        Ezeknél a forgatásoknál a kód már lejárt, és kevesebb eszköz jött vissza, mint amennyi
        kiment. Írd le, mi lett a megoldás, és ha rendeződött, jelöld készre - onnantól nem jelenik
        meg itt.
      </p>
      {hiba && (
        <p className="mb-3 rounded-[var(--radius)] border border-text-danger/40 bg-surface-2 px-3 py-2 text-[13px] text-text-danger">
          {hiba}
        </p>
      )}
      <div className="space-y-4">
        {hianyok.map((h) => (
          <div key={h.id} className="rounded-[var(--radius)] border border-border bg-surface-2 p-3">
            <p className="text-[14px] font-medium text-text-primary">
              {h.projekt_nev ?? `Kivitel #${h.id}`}
              {h.forgatas_datuma && (
                <span className="ml-2 text-[12.5px] font-normal text-text-secondary">
                  Forgatás: {new Date(h.forgatas_datuma).toLocaleDateString("hu-HU")}
                </span>
              )}
              <span className="ml-2 font-mono text-[12px] font-normal text-text-muted">({h.kod})</span>
            </p>
            <ul className="mt-2 space-y-1">
              {h.tetelek.map((t, i) => (
                <li key={i} className="flex items-center justify-between gap-3 text-[13px]">
                  <span className="min-w-0 truncate text-text-primary">{t.nev}</span>
                  <span className="shrink-0 text-text-danger">
                    hiányzik {t.hiany_db} db
                    <span className="ml-1.5 text-[12px] text-text-muted">
                      (kivitt {t.kivitt_db}, vissza {t.visszahozott_db})
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            {h.megjegyzes && (
              <p className="mt-2 text-[12.5px] text-text-secondary">
                <span className="text-text-muted">Észrevétel a lezáráskor:</span> {h.megjegyzes}
              </p>
            )}
            <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-start">
              <textarea
                value={megoldasok.get(h.id) ?? ""}
                onChange={(e) =>
                  setMegoldasok((elozo) => {
                    const uj = new Map(elozo);
                    uj.set(h.id, e.target.value);
                    return uj;
                  })
                }
                rows={2}
                placeholder="Mi lett a megoldás? (pl. megkerült, kifizettette, pótoltuk…)"
                className="w-full flex-1 rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-2 text-[13px] text-text-primary focus:outline-none"
              />
              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  disabled={busyId === h.id}
                  onClick={() => void ment(h.id, false)}
                  className="rounded-[var(--radius)] border border-border px-3 py-2 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                >
                  Magyarázat mentése
                </button>
                <button
                  type="button"
                  disabled={busyId === h.id}
                  onClick={() => void ment(h.id, true)}
                  className="rounded-[var(--radius)] bg-text-success/90 px-3 py-2 text-[13px] font-semibold text-surface-1 hover:opacity-90 disabled:opacity-50"
                >
                  Kész - megoldva
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
