"use client";

import { useState } from "react";
import { ModalReteg } from "@/components/ModalReteg";
import { authFetch } from "@/lib/authFetch";

/** VAN-e már utómunkája a projektnek? A hiba itt nem hiba: bizonytalanság
 * esetén false-t adunk, és a kérdés egyszerűen elmarad - a diszpó-küldés
 * sikerét semmi nem zavarhatja meg. */
export async function nincsUtomunkaja(projectId: number): Promise<boolean> {
  try {
    const res = await authFetch(`/api/v1/deliverables?project_id=${projectId}&limit=1`);
    if (!res.ok) return false;
    const sorok = (await res.json()) as unknown[];
    return Array.isArray(sorok) && sorok.length === 0;
  } catch {
    return false;
  }
}

/** Az ELŐZETES DISZPÓ első kiküldése utáni kérdés (a felhasználó kérése): ha
 * a projekthez még nincs utómunka, vezessük-e fel most - igenre a meglévő
 * create-utomunka végpont hozza létre (ugyanaz, mint a projekt "Utómunka"
 * gombja), és az anyag rögtön meg is nyílik.
 *
 * A hívó FELTÉTELESEN rendereli ({nyitva && ...}) - minden megnyitás friss
 * példány. */
export function UtomunkaFelvezetesKerdes({
  projectId,
  onClose,
  utomunkaElotag = "/utomunka/",
}: {
  projectId: number;
  onClose: () => void;
  /** Hova nyíljon a felvezetett utómunka - a felugró (embed) nézetben az
   * /embed/utomunka/ útvonal, hogy a modálon belül maradjunk. */
  utomunkaElotag?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  /** Utómunka felvezetése és MEGNYITÁSA. Kemény navigáció (nem router.push):
   * a modál-zárás history.back()-je és az élő frissítés is elütné a
   * kliens-oldali átirányítást (lásd FeldarabolasGomb) - a location.replace
   * a modál mesterséges history-rétegét is felülírja. */
  async function felvezet() {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/projects/${projectId}/create-utomunka`, { method: "POST" });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.id) {
        setHiba(String(data?.detail ?? `Sikertelen (HTTP ${res.status})`));
        return;
      }
      window.location.replace(`${utomunkaElotag}${data.id}`);
    } catch (err) {
      setHiba(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <ModalReteg onClose={busy ? undefined : onClose}>
      <div
        className="my-auto w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-2 text-[15px] font-medium text-text-primary">
          Az előzetes diszpó kiment - vezessünk fel utómunkát is?
        </h3>
        <p className="mb-4 text-[13px] leading-relaxed text-text-secondary">
          Ehhez a projekthez még nincs utómunka-anyag. Ha most felvezeted, rögtön meg is nyílik, és a vágók már
          látják a feladatot. (Később a projekt &quot;Utómunka&quot; gombjával is megteheted.)
        </p>
        {hiba && <p className="mb-3 text-[12.5px] text-text-danger">{hiba}</p>}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            Most nem
          </button>
          <button
            type="button"
            onClick={() => void felvezet()}
            disabled={busy}
            className="btn btn-primary disabled:opacity-50"
          >
            {busy ? "Felvezetés…" : "Utómunka felvezetése és megnyitása"}
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
