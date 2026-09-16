import { BekuldoOldal } from "@/components/anyagbekeres/BekuldoOldal";

/** ANYAGBEKÉRŐ - publikus beküldői oldal (bejelentkezés nélkül, tokenes
 * link, lásd middleware PUBLIC_PATHS). A teljes folyamat a kliens-
 * komponensben él: adatok + mappás feltöltés, videóigények, véglegesítés. */
export default async function AnyagbekeresOldal({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <BekuldoOldal bekeresToken={token} />;
}
