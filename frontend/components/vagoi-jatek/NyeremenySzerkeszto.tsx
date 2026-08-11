"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Gift } from "lucide-react";
import { authFetch } from "@/lib/authFetch";
import { ModalReteg } from "@/components/ModalReteg";

/** A hónap nyereményének kihirdetése.
 *
 * Ha még nincs meghirdetve, a gomb HANGSÚLYOS és a szöveg is szól érte: a
 * verseny akkor működik, ha a hónap elején tudják, miért mennek. Egy néma,
 * üres mező erre nem elég emlékeztető. */
export function NyeremenySzerkeszto({
  ev,
  honap,
  nyeremeny,
  megjegyzes,
}: {
  ev: number;
  honap: number;
  nyeremeny: string | null;
  megjegyzes: string | null;
}) {
  const [nyitva, setNyitva] = useState(false);
  const hianyzik = !nyeremeny;

  return (
    <>
      <button
        type="button"
        onClick={() => setNyitva(true)}
        className={hianyzik ? "btn btn-primary !text-[13px]" : "btn btn-ghost !text-[13px]"}
      >
        <Gift size={14} className="mr-1.5" />
        {hianyzik ? "Nyeremény kihirdetése" : "Nyeremény szerkesztése"}
      </button>
      {nyitva && (
        <NyeremenyUrlap
          ev={ev}
          honap={honap}
          nyeremeny={nyeremeny}
          megjegyzes={megjegyzes}
          onBezar={() => setNyitva(false)}
        />
      )}
    </>
  );
}

function NyeremenyUrlap({
  ev,
  honap,
  nyeremeny,
  megjegyzes,
  onBezar,
}: {
  ev: number;
  honap: number;
  nyeremeny: string | null;
  megjegyzes: string | null;
  onBezar: () => void;
}) {
  const router = useRouter();
  const [ertek, setErtek] = useState(nyeremeny ?? "");
  const [jegyzet, setJegyzet] = useState(megjegyzes ?? "");
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  async function mentes() {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch("/api/v1/vagoi-jatek/nyeremeny", {
        method: "PUT",
        body: JSON.stringify({ ev, honap, nyeremeny: ertek.trim() || null, megjegyzes: jegyzet.trim() || null }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setHiba(detail?.detail ?? `Sikertelen mentés (HTTP ${res.status})`);
        return;
      }
      onBezar();
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  const mezoClass =
    "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

  return (
    <ModalReteg onClose={busy ? undefined : onBezar}>
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-[14px] font-medium text-text-primary">A hónap nyereménye</h3>
          <p className="mt-0.5 text-[12px] text-text-muted">
            Ezt kapja, aki a hónap végén a legtöbb pontot gyűjtötte.
          </p>
        </div>
        <div className="space-y-3 p-5">
          {hiba && <p className="text-[12.5px] text-text-danger">{hiba}</p>}
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Nyeremény</label>
            <input
              value={ertek}
              onChange={(e) => setErtek(e.target.value)}
              disabled={busy}
              autoFocus
              placeholder="pl. egy szabadnap, vacsora, 20 000 Ft utalvány"
              className={mezoClass}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Megjegyzés</label>
            <input
              value={jegyzet}
              onChange={(e) => setJegyzet(e.target.value)}
              disabled={busy}
              placeholder="feltételek, részletek"
              className={mezoClass}
            />
          </div>
        </div>
        <div className="flex justify-end gap-3 border-t border-border px-5 py-3">
          <button type="button" onClick={onBezar} disabled={busy} className="btn btn-ghost">
            Mégse
          </button>
          <button type="button" onClick={mentes} disabled={busy} className="btn btn-primary">
            {busy ? "Mentés…" : "Mentés"}
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
