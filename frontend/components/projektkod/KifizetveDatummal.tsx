"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { StatusBadge } from "@/components/StatusBadge";
import { authFetch } from "@/lib/authFetch";
import { vedettOverlayZaras } from "@/lib/vedettOverlayZaras";

/** "Kifizetve" kapcsoló a projektkód kiadás-listájában, DÁTUM-KÉRDÉSSEL (a
 * felhasználó kérése): egy dátum nélkül felvezetett kiadás csak a
 * projektkódon él - a Kifizetve átállításakor itt kérdezzük meg a fizetés
 * dátumát, és azzal együtt mentjük, így kerül dátummal a kiadások közé.
 * Dátumos tételnél sima egykattintásos váltás (mint a KattinthatoAllapot). */
export function KifizetveDatummal({
  patchPath,
  kifizetve,
  vanDatum,
}: {
  patchPath: string;
  kifizetve: boolean;
  /** Van-e már dátuma a tételnek - ha nincs, a kifizetéshez bekérdezzük. */
  vanDatum: boolean;
}) {
  const router = useRouter();
  const [ertek, setErtek] = useState(kifizetve);
  const [propErtek, setPropErtek] = useState(kifizetve);
  const [busy, setBusy] = useState(false);
  const [datumKerdes, setDatumKerdes] = useState(false);
  const [datum, setDatum] = useState(() => new Date().toISOString().slice(0, 10));

  if (kifizetve !== propErtek) {
    setPropErtek(kifizetve);
    setErtek(kifizetve);
  }

  async function ment(body: Record<string, unknown>, uj: boolean) {
    const elozo = ertek;
    setErtek(uj);
    setBusy(true);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify(body) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setErtek(elozo);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      setErtek(elozo);
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  function katt() {
    if (busy) return;
    if (!ertek && !vanDatum) {
      // Dátum nélküli tétel kifizetése: előbb a fizetés dátumát kérdezzük.
      setDatum(new Date().toISOString().slice(0, 10));
      setDatumKerdes(true);
      return;
    }
    void ment({ kesz: !ertek }, !ertek);
  }

  return (
    <>
      {/* Nyitott tételen nem felirat, hanem FIZETÉS gomb áll (a felhasználó
          kérése) - kifizetés után a zöld Kifizetve jelölő, ami kattintva
          vissza is vonható. */}
      {ertek ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            katt();
          }}
          disabled={busy}
          title="Kattints a kifizetés visszavonásához"
          className="disabled:opacity-50"
        >
          <StatusBadge label="Kifizetve" tone="success" />
        </button>
      ) : (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            katt();
          }}
          disabled={busy}
          title="Kifizetettnek jelölés - dátum nélküli tételnél a fizetés dátumát is bekérdezi"
          className="rounded-[var(--radius)] border border-text-accent/50 px-3 py-1 text-[12.5px] font-medium text-text-accent hover:bg-bg-accent disabled:opacity-50"
        >
          Fizetés
        </button>
      )}
      {datumKerdes && (
        <KerdesOverlay onZaras={() => setDatumKerdes(false)}>
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-sm rounded-[var(--radius-lg)] border border-border bg-surface-2 p-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-2 text-[14px] font-medium text-text-primary">Mikor lett kifizetve?</h3>
            <p className="mb-3 text-[13px] text-text-secondary">
              Ennek a kiadásnak még nincs dátuma - a fizetés dátumával együtt kerül a kiadások közé.
            </p>
            <input
              type="date"
              value={datum}
              autoFocus
              onChange={(e) => setDatum(e.target.value)}
              className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-2 text-[13px] text-text-primary focus:outline-none"
            />
            <div className="mt-4 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setDatumKerdes(false)}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
              >
                Mégse
              </button>
              <button
                type="button"
                disabled={!datum}
                onClick={() => {
                  setDatumKerdes(false);
                  void ment({ kesz: true, kiadas_datuma: datum }, true);
                }}
                className="rounded-[var(--radius)] bg-[var(--accent-solid)] px-4 py-1.5 text-[13px] font-medium text-white hover:opacity-90 disabled:opacity-60"
              >
                Kifizetve ekkor
              </button>
            </div>
          </div>
        </KerdesOverlay>
      )}
    </>
  );
}

/** A dátum-kérdés overlay-e: a védett zárás (lenyomás+felengedés is rajta)
 * mellett MINDEN kattintást elnyel, hogy a táblázat-sor linkje ne kapja meg -
 * a kapcsoló egy kattintható soron belül él. */
function KerdesOverlay({ onZaras, children }: { onZaras: () => void; children: React.ReactNode }) {
  const zaras = vedettOverlayZaras(onZaras);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
      onMouseDown={(e) => {
        e.stopPropagation();
        zaras.onMouseDown?.(e);
      }}
      onClick={(e) => {
        e.stopPropagation();
        zaras.onClick?.(e);
      }}
    >
      {children}
    </div>
  );
}
