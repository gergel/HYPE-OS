"use client";

import { Search } from "lucide-react";

// A szűrés maga a közös, ékezet-érzéketlen szabályt használja - ugyanazt,
// amivel a DataTable keresője is dolgozik.
export { illeszkedik } from "@/lib/szoveg";

/** Szabadszavas kereső azokhoz a listákhoz, amik NEM a DataTable-t használják.
 *
 * A DataTable-nek van saját keresője (`filterable`), de van néhány lista, ami
 * kártyákból vagy lenyitható panelekből áll - ott ugyanez a mező kézzel kell.
 * Ez a komponens csak a mezőt adja: a szűrés a hívónál marad, mert minden
 * listánál más, MIBEN érdemes keresni (lásd `illeszkedik`).
 */
export function ListaKereso({
  ertek,
  onValtozas,
  placeholder,
  talalat,
  osszes,
  szeles = "w-80",
}: {
  ertek: string;
  onValtozas: (uj: string) => void;
  placeholder: string;
  /** Hány sor maradt a szűrés után - csak akkor írjuk ki, ha van keresés. */
  talalat: number;
  osszes: number;
  szeles?: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="relative">
        <Search size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
        <input
          type="search"
          value={ertek}
          onChange={(e) => onValtozas(e.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
          className={`${szeles} rounded-[var(--radius)] border border-border bg-surface-2 py-1.5 pl-7 pr-2 text-[13px] text-text-primary focus:outline-none`}
        />
      </label>
      {/* A találatszám csak keresés közben érdekes: enélkül nem derül ki, hogy
          egy üres lista azért üres, mert nincs ilyen, vagy mert elgépelték. */}
      {ertek.trim() !== "" && (
        <span className="text-[12.5px] text-text-muted">
          {talalat} / {osszes} találat
        </span>
      )}
    </div>
  );
}
