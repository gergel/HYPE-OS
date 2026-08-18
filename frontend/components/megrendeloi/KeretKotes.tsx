"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { KeresosSelect } from "@/components/KeresosSelect";
import { StatusBadge } from "@/components/StatusBadge";
import type { MegrendeloiKeret } from "@/lib/api";

/** "Ez a munka keretszerződés alatt van" - a projektkód rákötése a megrendelői
 * keretszerződésre.
 *
 * Miért kell külön kimondani? Mert korábban a rendszer MAGÁTÓL állította ezt
 * minden olyan projektkódról, aminek az ügyfelével volt bárhol keretszerződés -
 * és ez tömegesen hazudott: egyetlen kerettől a megrendelő összes munkája
 * "keretszerződés alatt"-nak látszott. Ez a jelölés viszont TEENDŐT tüntet el
 * (eseti szerződést nem kérünk), tehát tévesen állítva pont a hiányzó papírokat
 * rejti el.
 *
 * Mostantól a kötés a projektkódon él: vagy a Notion-import hozza, vagy itt
 * mondja ki valaki. Ha megvan, a szerződés-lépés kész, és már csak a TIG kell. */
export function KeretKotes({
  projectCodeId,
  keretFedi,
  keretek,
  keretszerzodesId,
  canEdit,
}: {
  projectCodeId: number;
  keretFedi: boolean;
  /** A választható megrendelői keretszerződések (cégenként). */
  keretek: MegrendeloiKeret[];
  /** A projektkódhoz KÖTÖTT keret azonosítója, ha van. */
  keretszerzodesId: number | null;
  canEdit: boolean;
}) {
  const router = useRouter();
  const [valasztott, setValasztott] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [hiba, setHiba] = useState<string | null>(null);

  const kotott = keretek.find((k) => k.id === keretszerzodesId);

  async function ment(keretszerzodes_id: number | null) {
    setBusy(true);
    setHiba(null);
    try {
      const res = await authFetch(`/api/v1/megrendeloi-papirok/keret-kotes/${projectCodeId}`, {
        method: "POST",
        body: JSON.stringify({ keretszerzodes_id }),
      });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        setHiba(reszlet?.detail ?? `Sikertelen mentés (HTTP ${res.status})`);
        return;
      }
      router.refresh();
    } catch (err) {
      setHiba(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (keretFedi) {
    return (
      <div className="space-y-1 rounded-[var(--radius)] border border-border p-3">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label="Keretszerződés alatt" tone="success" />
          <span className="text-[13px] text-text-secondary">
            {kotott?.ceg_neve ?? kotott?.client_nev ?? "keretszerződés"}
          </span>
        </div>
        <p className="text-[12.5px] text-text-muted">
          Eseti szerződés nem kell – már csak a TIG van hátra.
        </p>
        {canEdit && (
          <button
            type="button"
            disabled={busy}
            onClick={() => ment(null)}
            className="text-[12px] text-text-muted hover:text-text-primary disabled:opacity-50"
          >
            Mégsem tartozik keret alá
          </button>
        )}
        {hiba && <p className="text-[12px] text-text-danger">{hiba}</p>}
      </div>
    );
  }

  if (!canEdit || keretek.length === 0) return null;

  return (
    <div className="space-y-2 rounded-[var(--radius)] border border-border p-3">
      <p className="text-[12.5px] text-text-secondary">
        Keretszerződés alá tartozik? Válaszd ki, kivel – utána nincs más teendő, csak a TIG.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <KeresosSelect
          value={valasztott}
          options={keretek.map((k) => ({
            value: String(k.id),
            label: k.ceg_neve ?? k.client_nev ?? `#${k.id}`,
          }))}
          onChange={(ertek) => setValasztott(ertek)}
          placeholder="Keretszerződés keresése…"
          className="min-w-[220px]"
          disabled={busy}
        />
        <button
          type="button"
          disabled={!valasztott || busy}
          onClick={() => ment(Number(valasztott))}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          {busy ? "Mentés…" : "Keret alá teszem"}
        </button>
      </div>
      {hiba && <p className="text-[12px] text-text-danger">{hiba}</p>}
    </div>
  );
}
