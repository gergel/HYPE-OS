import { AllapotFeltoltes } from "@/components/auto-allapot/AllapotFeltoltes";

/** AUTÓ ÁLLAPOTFOTÓK - publikus bekérő oldal (bejelentkezés nélkül, tokenes
 * link, lásd middleware PUBLIC_PATHS és backend routes/auto_allapot.py). */
export default async function AutoAllapotBekeresOldal({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <AllapotFeltoltes token={token} />;
}
