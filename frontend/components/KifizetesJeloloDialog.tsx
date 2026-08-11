"use client";

import { useState } from "react";
import { ModalReteg } from "@/components/ModalReteg";

/** "Kifizetve jelölés" - és a hozzá tartozó egyetlen döntés: keletkezzen-e
 * Kiadás sor a Pénzügyben.
 *
 * Miért kérdés ez egyáltalán? Mert a kifizetés ténye és a kiadás nyilvántartása
 * két külön dolog. Alapból a kettő együtt jár: a jelölés létrehozza a Kiadás
 * sort, és onnantól a Pénzügy összesítőiben is ott a költség. Van viszont, ami
 * MÁSHOL van elszámolva (a bank- vagy a könyvelői oldalon már szerepel) - ott
 * egy itteni Kiadás sor megkétszerezné az összeget, miközben a papírnak
 * ugyanúgy „kifizetve” állapotba kell kerülnie, hogy ne maradjon teendőként a
 * havi listán.
 *
 * A hívó FELTÉTELESEN rendereli, így minden megnyitás friss példány. */
export function KifizetesJeloloDialog({
  nev,
  osszeg,
  onMegse,
  onJelol,
}: {
  /** Kinek a papírjáról van szó - a megerősítés ettől lesz ellenőrizhető. */
  nev: string;
  /** Mennyiről (már formázva). Üresen elhagyjuk a sort. */
  osszeg?: string | null;
  onMegse: () => void;
  onJelol: (kiadasbaKerul: boolean) => void;
}) {
  const [kiadasbaKerul, setKiadasbaKerul] = useState(true);

  return (
    <ModalReteg onClose={onMegse}>
      <div
        role="dialog"
        aria-modal="true"
        className="w-full max-w-md rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border px-5 py-3">
          <h3 className="text-[14px] font-medium text-text-primary">Kifizetve jelölés – {nev}</h3>
          {osszeg && <p className="mt-0.5 text-[12.5px] text-text-secondary">{osszeg}</p>}
        </div>

        <div className="p-5">
          <label className="flex cursor-pointer items-start gap-2.5">
            <input
              type="checkbox"
              checked={kiadasbaKerul}
              onChange={(e) => setKiadasbaKerul(e.target.checked)}
              className="mt-0.5"
            />
            <span className="text-[13px] text-text-primary">
              Kerüljön be a Pénzügy → Kiadások közé
              <span className="mt-0.5 block text-[12px] text-text-muted">
                Ez hozza létre (vagy frissíti) a Kiadás sort, és így számít bele a pénzügyi összesítőkbe.
              </span>
            </span>
          </label>

          {!kiadasbaKerul && (
            <p className="mt-3 rounded-[var(--radius)] border border-border bg-surface-3 p-3 text-[12.5px] text-text-secondary">
              A papír „kifizetve” lesz, de <b>nem keletkezik Kiadás sor</b> – akkor válaszd ezt, ha a költség máshol
              (bankban, könyvelésnél) már el van számolva, és itt csak duplázná az összeget.
            </p>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-border px-5 py-3">
          <button
            type="button"
            onClick={onMegse}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
          >
            Mégse
          </button>
          <button
            type="button"
            onClick={() => onJelol(kiadasbaKerul)}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90"
          >
            Kifizetve jelölés
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
