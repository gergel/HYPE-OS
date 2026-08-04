/** Stabil (értékenként mindig ugyanaz), de tetszőleges string-készlethez
 * használható színpaletta - a Notion "select" mezők eredeti színeit nem
 * tároltuk el importáláskor, ezért egy determinisztikus hash-alapú
 * kiosztással közelítjük a színes címke-hatást (lásd EditableDetailGrid).
 *
 * Külön fájl (nem lib/detail.tsx), mert ezt kliens-komponens (EditableDetailGrid)
 * is importálja futásidőben - a lib/detail.tsx a lib/api.ts-en (next/headers,
 * csak Server Component-ekben elérhető) keresztül szerver-only kódot húzna be. */
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

export function selectColor(value: string): { bg: string; text: string } {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return SELECT_COLOR_PALETTE[Math.abs(hash) % SELECT_COLOR_PALETTE.length];
}
