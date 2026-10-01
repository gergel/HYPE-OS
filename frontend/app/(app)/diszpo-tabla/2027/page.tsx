import { DiszpoTablaOldal } from "@/components/DiszpoTablaOldal";

/** A HYPE 2027 tábla (a felhasználó kérése): belsős (az új névsorral), külsős
 * (a 2026-os nevekkel) és AnyDesk lap - a 2026-osnál átláthatóbb, „rendezett”
 * ráccsal (lásd DiszpoTablaRacs `rendezett`). */
export default async function DiszpoTabla2027Page({ searchParams }: { searchParams: Promise<{ lap?: string }> }) {
  const { lap } = await searchParams;
  return <DiszpoTablaOldal ev={2027} alap="/diszpo-tabla/2027" lap={lap} rendezett />;
}
