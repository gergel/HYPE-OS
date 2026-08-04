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
};

export function humanizeKey(key: string): string {
  if (LABEL_OVERRIDES[key]) return LABEL_OVERRIDES[key];
  return key
    .replace(/_id$/, "")
    .replace(/_/g, " ")
    .replace(/^./, (c) => c.toUpperCase());
}
