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
  // Kiadás: a `megnevezes` a felületen "Cégnév" (azt a kiadás-oldalak
  // helyben írják át, mert a megnevezes kulcsot más entitások is használják),
  // a kiadas_leiras pedig a "mire ment" - lásd backend models/finance.Expense.
  kiadas_leiras: "Megnevezés (mire ment)",
  afa_szazalek: "ÁFA %",
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
  kiosztott_nevek: "Kiosztva",
  kiosztott_employee_ids: "Kiosztva (azonosítók)",
  vinyok: "Vinyók",
  vagas_leiras: "Vágás leírása",
  time_minutes: "Vágással töltött perc",
  koltseg: "Költség",
  esemeny_neve: "Esemény neve",
  projektkod_szoveg: "Projektkód",
  // Szerződés- és munkatárs-adatlapok: az angol/nyers oszlopnevek ("Full
  // name", "Is active", "Szerzodes file url") zavaróak voltak a mezőrácsban
  // (a felhasználó hibajelzése) - itt kapnak érthető magyar címkét.
  full_name: "Teljes név",
  is_active: "Aktív munkatárs",
  nev: "Név",
  ceg_neve: "Cég neve",
  szekhely: "Székhely",
  adoszam: "Adószám",
  keltezes: "Keltezés",
  alairva: "Aláírva visszaérkezett",
  keretszerzodes: "Keretszerződés-e",
  aktiv: "Aktív",
  tipus: "Típus",
  szerzodes_allapota: "Szerződés állapota",
  szerzodes_megjegyzes: "Megjegyzés a szerződéshez",
  szerzodes_file_url: "Szerződés dokumentuma (link)",
  szerzodes_file_storage_key: "Szerződés tárhely-kulcsa (technikai)",
  alairt_file_url: "Aláírt példány (link)",
  alairt_file_storage_key: "Aláírt példány tárhely-kulcsa (technikai)",
  teljesites_szoveg: "Teljesítés ideje",
  teljesites_kezdete: "Teljesítés kezdete (régi adat)",
  teljesites_vege: "Teljesítés vége (régi adat)",
  netto_osszeg: "Nettó összeg",
  vallalkozas_kepviseloje: "Vállalkozás képviselője",
  vallalkozas_nyilvantartasi_szam: "Vállalkozás nyilvántartási száma",
  keretszerzodes_kuld: "Keretszerződés kiküldendő",
  created_at_notion: "Létrehozva (Notion, technikai)",
  letrehozta_notion: "Létrehozta (Notion, technikai)",
  kihagyas_indoka: "Kihagyás indoka",
};

export function humanizeKey(key: string): string {
  if (LABEL_OVERRIDES[key]) return LABEL_OVERRIDES[key];
  return key
    .replace(/_id$/, "")
    .replace(/_/g, " ")
    .replace(/^./, (c) => c.toUpperCase());
}
