/** Stabil (értékenként mindig ugyanaz), de tetszőleges string-készlethez
 * használható színpaletta - a Notion "select" mezők eredeti színeit nem
 * tároltuk el importáláskor, ezért egy determinisztikus hash-alapú
 * kiosztással közelítjük a színes címke-hatást (lásd EditableDetailGrid).
 *
 * Külön fájl (nem lib/detail.tsx), mert ezt kliens-komponens (EditableDetailGrid)
 * is importálja futásidőben - a lib/detail.tsx a lib/api.ts-en (next/headers,
 * csak Server Component-ekben elérhető) keresztül szerver-only kódot húzna be. */
const SELECT_COLOR_PALETTE: { bg: string; text: string }[] = [
  { bg: "var(--bg-accent)", text: "var(--text-accent)" },
  { bg: "var(--bg-success)", text: "var(--text-success)" },
  { bg: "var(--bg-warning)", text: "var(--text-warning)" },
  { bg: "var(--bg-danger)", text: "var(--text-danger)" },
  { bg: "rgba(168, 85, 247, 0.14)", text: "#d8b4fe" },
  { bg: "rgba(236, 72, 153, 0.14)", text: "#f9a8d4" },
  { bg: "rgba(20, 184, 166, 0.14)", text: "#5eead4" },
  { bg: "rgba(234, 179, 8, 0.14)", text: "#fde047" },
  { bg: "rgba(99, 102, 241, 0.14)", text: "#a5b4fc" },
  { bg: "rgba(163, 163, 163, 0.14)", text: "#d4d4d8" },
];

export function selectColor(value: string): { bg: string; text: string } {
  let hash = 0;
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) | 0;
  }
  return SELECT_COLOR_PALETTE[Math.abs(hash) % SELECT_COLOR_PALETTE.length];
}
