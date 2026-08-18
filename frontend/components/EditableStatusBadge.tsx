"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { SelectDropdown } from "@/components/SelectDropdown";
import { authFetch } from "@/lib/authFetch";

/** Egy állapot-jellegű (select típusú) mező színes "pill" alakban, ami
 * kattintás nélkül is azonnal legördíthető és szerkeszthető (lásd
 * SelectDropdown) - kompakt, lista-sorokba és fejlécekbe is beágyazható
 * formában (lásd DetailHeader, illetve a lista nézetek Állapot oszlopa).
 * Táblázat-sorban használva megállítja az eseményt, hogy a legördülő
 * megnyitása ne indítsa el a sor kattintására beállított navigációt (lásd
 * RowLink). */
export function EditableStatusBadge({
  patchPath,
  field,
  value,
  options,
  placeholder = "Nincs állapot",
}: {
  patchPath: string;
  field: string;
  value: string | null;
  options: string[];
  placeholder?: string;
}) {
  const router = useRouter();
  // AZONNAL az új értéket mutatjuk, és csak utána mentünk ("optimista"
  // frissítés). Enélkül a felület a szerver válaszára és a teljes oldal
  // újrarenderelésére várt, tehát egy állapot átállítása másodpercekig úgy
  // nézett ki, mintha nem történt volna semmi - egy nagyobb listán pláne.
  // Hibánál visszaáll a régi érték, tehát hazudni nem tud.
  const [ertek, setErtek] = useState(value);
  const [propErtek, setPropErtek] = useState(value);
  const [, indit] = useTransition();

  // Ha a szerver adata megjön (vagy máshonnan változik), az az igazság.
  if (value !== propErtek) {
    setPropErtek(value);
    setErtek(value);
  }

  async function onChange(next: string | null) {
    const elozo = ertek;
    setErtek(next);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify({ [field]: next }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setErtek(elozo);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      // A frissítés átmenetben fut: a lista közben használható marad, nem
      // fagy le arra az időre, amíg a szerver újraszámolja az oldalt.
      indit(() => router.refresh());
    } catch (err) {
      setErtek(elozo);
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    }
  }

  return (
    <span onClick={(e) => e.stopPropagation()}>
      <SelectDropdown value={ertek} options={options} onChange={onChange} placeholder={placeholder} />
    </span>
  );
}
