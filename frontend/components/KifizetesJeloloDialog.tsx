"use client";

import { useState } from "react";
import { ModalReteg } from "@/components/ModalReteg";

/** A mai nap ISO alakban, HELYI idő szerint - a `toISOString()` UTC-re vált, és
 * este 10 után már a következő napot adná vissza. */
function maiNap(): string {
  const most = new Date();
  return `${most.getFullYear()}-${String(most.getMonth() + 1).padStart(2, "0")}-${String(most.getDate()).padStart(2, "0")}`;
}

/** "Kifizetve jelölés" - a hozzá tartozó két adattal: MIKOR ment el a pénz, és
 * keletkezzen-e Kiadás sor a Pénzügyben.
 *
 * A DÁTUM azért kérdés, mert a jelölés ritkán esik egybe az utalással: a
 * banki átutalás megtörténik, a rendszerben pedig csak napokkal később kattint
 * rá valaki. Ha ilyenkor mindig a mai nap kerülne be, a pénzügyi kimutatásban
 * rossz napon (rosszabb esetben rossz hónapban) állna a tétel. Alapból ezért a
 * mai nap van kitöltve, de át lehet írni.
 *
 * A KIADÁS SOR azért kérdés, mert a kifizetés ténye és a kiadás nyilvántartása
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
  hatarido,
  onMegse,
  onJelol,
}: {
  /** Kinek a papírjáról van szó - a megerősítés ettől lesz ellenőrizhető. */
  nev: string;
  /** Mennyiről (már formázva). Üresen elhagyjuk a sort. */
  osszeg?: string | null;
  /** A számla fizetési határideje (ISO), ha ismert - csak tájékoztatásul, hogy
   * a dátum megadásakor látszódjon, mihez képest utaltunk. */
  hatarido?: string | null;
  onMegse: () => void;
  onJelol: (kiadasbaKerul: boolean, kifizetesDatuma: string) => void;
}) {
  const [kiadasbaKerul, setKiadasbaKerul] = useState(true);
  const [kifizetesDatuma, setKifizetesDatuma] = useState(maiNap());

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
          <label className="block text-[13px] text-text-primary">
            Mikor lett kifizetve
            <input
              type="date"
              value={kifizetesDatuma}
              onChange={(e) => setKifizetesDatuma(e.target.value)}
              className="mt-1 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1.5 text-[13px] text-text-primary"
            />
            <span className="mt-0.5 block text-[12px] text-text-muted">
              A tényleges utalás napja – ez kerül a Kiadás sorra is.
              {hatarido && ` Fizetési határidő: ${hatarido}.`}
            </span>
          </label>

          <label className="mt-4 flex cursor-pointer items-start gap-2.5">
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
            disabled={!kifizetesDatuma}
            onClick={() => onJelol(kiadasbaKerul, kifizetesDatuma)}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            Kifizetve jelölés
          </button>
        </div>
      </div>
    </ModalReteg>
  );
}
