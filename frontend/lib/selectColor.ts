/** Stabil (értékenként mindig ugyanaz), de tetszőleges string-készlethez
 * használható színpaletta - a Notion "select" mezők eredeti színeit nem
 * tároltuk el importáláskor, ezért egy determinisztikus hash-alapú
 * kiosztással közelítjük a színes címke-hatást (lásd EditableDetailGrid).
 *
 * Külön fájl (nem lib/detail.tsx), mert ezt kliens-komponens (EditableDetailGrid)
 * is importálja futásidőben - a lib/detail.tsx a lib/api.ts-en (next/headers,
 * csak Server Component-ekben elérhető) keresztül szerver-only kódot húzna be. */
import { normalizal } from "@/lib/szoveg";

/* Tompított, egymáshoz hangolt tónusok: a címkéknek elég megkülönböztethetőnek
 * lenniük, nem kell kiabálniuk. Mind a globals.css kategória-tokenjeire épül,
 * hogy a paletta egy helyen legyen hangolható. */
const SELECT_COLOR_PALETTE: { bg: string; text: string }[] = [
  { bg: "var(--bg-blue)", text: "var(--text-blue)" },
  { bg: "var(--bg-success)", text: "var(--text-success)" },
  { bg: "var(--bg-warning)", text: "var(--text-warning)" },
  { bg: "var(--bg-danger)", text: "var(--text-danger)" },
  { bg: "var(--bg-teal)", text: "var(--text-teal)" },
  { bg: "var(--bg-pink)", text: "var(--text-pink)" },
  { bg: "var(--bg-orange)", text: "var(--text-orange)" },
  { bg: "var(--bg-yellow)", text: "var(--text-yellow)" },
  { bg: "var(--bg-accent)", text: "var(--text-accent)" },
  { bg: "var(--surface-4)", text: "var(--text-secondary)" },
];

const PIROS = { bg: "var(--bg-danger)", text: "var(--text-danger)" };
const ZOLD = { bg: "var(--bg-success)", text: "var(--text-success)" };

/** Amiknek a JELENTÉSE dönti el a színét, nem a hash.
 *
 * A hash-kiosztás azért van, hogy a sok, tetszőleges címke megkülönböztethető
 * legyen - de van pár érték, aminél a szín maga az információ: az "Elmaradt"
 * nem lehet véletlenül zöld, a "Van" nem lehet véletlenül piros. Ezeket
 * ékezet- és kisbetű-tűrően, a TELJES értékre nézzük (a "nem volt" nem
 * "volt"), egyedül az "elmarad" előtagot engedjük, mert oda gyakran kerül
 * zárójeles magyarázat ("Elmaradt (ügyfél lemondta)").
 *
 * Ugyanaz a szabály, mint a backend models/project_code.esemeny_elmaradt-ban:
 * ami ott "elmaradt", az itt piros. */
const KEK = { bg: "var(--bg-blue)", text: "var(--text-blue)" };

const SZEMANTIKUS_SZINEK: Record<string, { bg: string; text: string }> = {
  van: ZOLD,
  volt: ZOLD,
  megvolt: ZOLD,
  megtortent: ZOLD,
  // Az utómunka archiválás-mezője (a felhasználó kérése): az "Archiválható"
  // kék (még teendő van vele), az "Archiválva" zöld (kész).
  archivalhato: KEK,
  archivalva: ZOLD,
};

/** Lásd backend models/project_code.ELMARADT_ELOTAG - a kettőt együtt kell
 * módosítani, különben a felület mást mond, mint a papírozás szabálya. */
const ELMARADT_ELOTAG = "elmarad";

export function selectColor(value: string): { bg: string; text: string } {
  const kulcs = normalizal(value).trim();
  if (kulcs.startsWith(ELMARADT_ELOTAG)) return PIROS;
  const szemantikus = SZEMANTIKUS_SZINEK[kulcs];
  if (szemantikus) return szemantikus;

  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return SELECT_COLOR_PALETTE[Math.abs(hash) % SELECT_COLOR_PALETTE.length];
}
