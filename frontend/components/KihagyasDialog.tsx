"use client";

import { useState } from "react";
import { ModalReteg } from "@/components/ModalReteg";

/** Kihagyás INDOKLÁSSAL - felugró ablak, ami nem enged tovább üres mezővel.
 *
 * Egy hiányzó szerződés vagy TIG önmagában gyanús: a puszta "Kihagyva"
 * jelölésről fél év múlva senki nem tudja megmondani, hogy szándékos volt-e,
 * vagy elfelejtődött. Ezért a backend is kötelezővé teszi az indokot (lásd
 * routes/subcontractor_contracts.py skip_contract, performance_certificates.py
 * skip_tig) - ez az ablak csak azt biztosítja, hogy a felhasználó ne egy
 * hibaüzenetből tudja meg.
 *
 * A megerősítést szándékosan NEM a közös useConfirm() adja: az csak igen/nem
 * kérdést tud, itt viszont szöveget kell bekérni.
 *
 * A hívó FELTÉTELESEN rendereli ({nyitva && <KihagyasDialog .../>}), nem egy
 * `nyitva` propot kap: így minden megnyitás friss példányt jelent, üres
 * mezővel. Egy belső "nyitáskor ürítsd ki" effekt ugyanezt érné el, csak
 * fölösleges újrarendereléssel. */
export function KihagyasDialog({
  cim,
  leiras,
  onMegse,
  onKihagy,
}: {
  cim: string;
  leiras: string;
  onMegse: () => void;
  onKihagy: (indok: string) => void;
}) {
  const [indok, setIndok] = useState("");
  const [hiba, setHiba] = useState(false);

  function megerosit() {
    const tisztitott = indok.trim();
    if (!tisztitott) {
      setHiba(true);
      return;
    }
    onKihagy(tisztitott);
  }

  return (
    <ModalReteg onClose={onMegse}>
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-2 text-[14px] font-medium text-text-primary">{cim}</h3>
        <p className="mb-4 text-[13px] text-text-secondary">{leiras}</p>
        <label className="mb-1.5 block text-[11px] font-medium uppercase tracking-wide text-text-muted">
          A kihagyás oka
        </label>
        <textarea
          autoFocus
          rows={3}
          value={indok}
          onChange={(e) => {
            setIndok(e.target.value);
            if (hiba) setHiba(false);
          }}
          placeholder="Pl. a munkát a partnercég számlázza, nálunk nincs vele szerződés"
          className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary outline-none focus:border-text-accent/40"
        />
        {hiba && <p className="mt-1.5 text-[12px] text-text-danger">Az indoklás nem maradhat üresen.</p>}
        <div className="mt-5 flex justify-end gap-3">
          <button
            type="button"
            onClick={onMegse}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            Mégse
          </button>
          <button
            type="button"
            onClick={megerosit}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-primary hover:bg-surface-3"
          >
            Kihagyás
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
