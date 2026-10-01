import { DiszpoTablaOldal } from "@/components/DiszpoTablaOldal";

/** A HYPE 2026 tábla - lásd components/DiszpoTablaOldal. */
export default async function DiszpoTablaPage({ searchParams }: { searchParams: Promise<{ lap?: string }> }) {
  const { lap } = await searchParams;
  return <DiszpoTablaOldal ev={2026} alap="/diszpo-tabla" lap={lap} />;
}
