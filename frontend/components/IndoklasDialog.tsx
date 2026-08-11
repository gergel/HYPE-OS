"use client";

import { useState } from "react";
import { ModalReteg } from "@/components/ModalReteg";

/** Felugró ablak, ami INDOKLÁST kér, és üres mezővel nem enged tovább.
 *
 * Két helyen kell, ugyanazzal a logikával:
 *
 * - kihagyásnál (szerződés/TIG) - egy hiányzó papír önmagában gyanús: a puszta
 *   "Kihagyva" jelölésről fél év múlva senki nem tudná megmondani, szándékos
 *   volt-e vagy elfelejtődött;
 * - a "projekt kiadásként elszámolva" jelölésnél - enélkül a jelölés csak
 *   annyit mondana, hogy ettől az embertől nem kell papír, azt nem, hogy hol
 *   keressük a pénzt.
 *
 * Mindkettőnél a backend is megköveteli az indokot; ez az ablak csak azt
 * biztosítja, hogy a felhasználó ne egy hibaüzenetből tudja meg.
 *
 * A hívó FELTÉTELESEN rendereli ({nyitva && <IndoklasDialog .../>}), nem egy
 * `nyitva` propot kap: így minden megnyitás friss példányt jelent, üres
 * mezővel. Egy belső "nyitáskor ürítsd ki" effekt ugyanezt érné el, csak
 * fölösleges újrarendereléssel. */
export function IndoklasDialog({
  cim,
  leiras,
  mezoCimke = "Indoklás",
  placeholder,
  gombCimke,
  onMegse,
  onKesz,
}: {
  cim: string;
  leiras: string;
  mezoCimke?: string;
  placeholder?: string;
  gombCimke: string;
  onMegse: () => void;
  onKesz: (indok: string) => void;
}) {
  const [indok, setIndok] = useState("");
  const [hiba, setHiba] = useState(false);

  function megerosit() {
    const tisztitott = indok.trim();
    if (!tisztitott) {
      setHiba(true);
      return;
    }
    onKesz(tisztitott);
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
          {mezoCimke}
        </label>
        <textarea
          autoFocus
          rows={3}
          value={indok}
          onChange={(e) => {
            setIndok(e.target.value);
            if (hiba) setHiba(false);
          }}
          placeholder={placeholder}
          className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 text-[13px] text-text-primary outline-none focus:border-text-accent/40"
        />
        {hiba && <p className="mt-1.5 text-[12px] text-text-danger">Ez a mező nem maradhat üresen.</p>}
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
            {gombCimke}
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
