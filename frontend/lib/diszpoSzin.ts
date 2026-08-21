/** A diszpótábla cella-SZÍNEI - a jelentésükkel és a megjelenésükkel.
 *
 * A szín itt nem formázás, hanem ADAT: az mondja meg, ki melyik nap dolgozott,
 * és ebből számoljuk a havi munkanapokat (lásd backend
 * services/munkanap_szamlalo.py).
 *
 * MIÉRT KÜLÖN FÁJL? Mert ezt a KLIENS oldal is használja, a `lib/api.ts`-t
 * viszont nem hívhatja értékként: az `next/headers`-t húzna be (a modul
 * szerver oldalon süti-alapú hitelesítéssel hív), és a build elszállna.
 * Ugyanez a szétválasztás van a lib/utokovetes.ts-nél is. */

export const DISZPO_SZINEK = ["zold", "kek", "feher", "piros", "szurke"] as const;
export type DiszpoSzin = (typeof DISZPO_SZINEK)[number];

export type SzinLeiras = {
  cimke: string;
  jelentes: string;
  hatter: string;
  szoveg: string;
};

export const SZIN_LEIRAS: Record<DiszpoSzin, SzinLeiras> = {
  zold: {
    cimke: "Zöld",
    jelentes: "Aznap dolgozott (a vágóknál: terepen)",
    hatter: "#16a34a",
    szoveg: "#f0fdf4",
  },
  kek: {
    cimke: "Kék",
    jelentes: "A vágók munkanapja (irodában) – ez is munkanap",
    hatter: "#2563eb",
    szoveg: "#eff6ff",
  },
  feher: {
    cimke: "Fehér",
    jelentes: "Munkanap volt, de nem kapott munkát – ez is munkanap",
    hatter: "#e5e7eb",
    szoveg: "#111827",
  },
  piros: {
    cimke: "Piros",
    jelentes: "Nem munkanap (szabadnap)",
    hatter: "#dc2626",
    szoveg: "#fef2f2",
  },
  szurke: {
    cimke: "Szürke",
    jelentes: "Nem releváns (akkor még nem dolgozott nálunk)",
    hatter: "#6b7280",
    szoveg: "#f9fafb",
  },
};

/** MUNKANAPNAK számító színek. A fehér is köztük van: a napja le volt kötve,
 *  csak nem tudtunk rá munkát adni - a szerződött napokból ugyanúgy fogy. */
export const MUNKANAP_SZINEK: ReadonlySet<string> = new Set(["zold", "kek", "feher"]);

export const HONAP_NEVEK = [
  "január",
  "február",
  "március",
  "április",
  "május",
  "június",
  "július",
  "augusztus",
  "szeptember",
  "október",
  "november",
  "december",
];
