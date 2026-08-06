/** Mezőnév -> ember által olvasható címke.
 *
 * Szándékosan ÖNÁLLÓ, függőség nélküli modul: kliens-komponensek is
 * használják (lásd EntityFieldManager), a lib/detail.tsx viszont a lib/api.ts-en
 * keresztül a "next/headers"-t is behúzza, ami csak szerver-oldalon létezik -
 * onnan importálva a kliens-bundle összeomlana. */

/** Néhány Notion-ből importált mezőnév ékezet nélküli/kódolt (pl.
 * "vallakozas_neve"), ezért a humanizeKey generikus szó-szétbontása nem adna
 * helyes magyar címkét - ezekhez explicit felülírás kell. */
const LABEL_OVERRIDES: Record<string, string> = {
  vallakozas_neve: "Vállalkozás neve",
  vallalkozas_kepviselo: "Vállalkozás képviselője",
  vallakozas_szekhely: "Vállalkozás székhelye",
  vallalkozas_adoszama: "Vállalkozás adószáma",
  nyilvantartasi_szam: "Nyilvántartási szám",
  megbizas_targya: "Megbízás tárgya",
  plusz_afa: "Plusz ÁFA",
  munkaszerzodes_url: "Munkaszerződés",
  email: "Email cím",
  vagas_leallitva: "Vágás leállítva",
  naptar_szin: "Naptár szín",
  nem_diszponalando: "Nem diszponálandó (meeting)",
  // Utómunka-mezők - ezek a Vágó nézet kártyáin is megjelenhetnek, ott
  // különösen zavaró lenne az ékezet nélküli, nyers oszlopnév.
  projekt_neve: "Anyag neve",
  hatarido: "Határidő",
  allapot: "Állapot",
  anyag_kikuldve: "Anyag kiküldve",
  kesz_anyag_url: "Kész anyag linkje",
  nyersanyag_url: "Nyersanyag linkje",
  vago_employee_id: "Vágó",
  assigned_to_employee_id: "Kiosztva",
  vinyok: "Vinyók",
  vagas_leiras: "Vágás leírása",
  time_minutes: "Vágással töltött perc",
  koltseg: "Költség",
  esemeny_neve: "Esemény neve",
  projektkod_szoveg: "Projektkód",
};

export function humanizeKey(key: string): string {
  if (LABEL_OVERRIDES[key]) return LABEL_OVERRIDES[key];
  return key
    .replace(/_id$/, "")
    .replace(/_/g, " ")
    .replace(/^./, (c) => c.toUpperCase());
}
