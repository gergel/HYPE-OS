import type { Employee } from "@/lib/api";

/** Ki lehet egyáltalán SZÁMLÁZÓ FÉL egy projekten.
 *
 * Egyetlen kizáró ok van, és ezt a backend is ellenőrzi (lásd
 * routes/project_szamlazok.py set_szamlazo): a belsős munkatárs havi bérezésű,
 * nála nincs projektenkénti számlázás, tehát más nevében sem állíthat ki
 * számlát.
 *
 * Ami szándékosan NEM szűr:
 *
 * - a projekt stáblistája: a számlázó félnek semmi köze ahhoz, ki volt ott a
 *   forgatáson - gyakori, hogy a számlát olyan vállalkozó állítja ki, aki maga
 *   nem vett részt a munkában;
 * - az `is_active`: egy régi projekt papírját az akkori számlázó nevére kell
 *   kiállítani akkor is, ha azóta már nem dolgozunk vele. Kiszűrve a
 *   felhasználó egyszerűen nem találná meg azt, akit keres. */
export function szamlazokentValaszthatoak(emberek: Employee[]): { id: number; full_name: string }[] {
  return emberek
    .filter((e) => e.tipus !== "belsos")
    .map((e) => ({ id: e.id, full_name: e.full_name }));
}
