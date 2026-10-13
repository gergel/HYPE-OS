import type { Viewport } from "next";
import { AllapotFeltoltes } from "@/components/auto-allapot/AllapotFeltoltes";

/** Csak telefonon használják (a felhasználó kérése): fix, a kijelzőt kitöltő
 * oldal - nem nagyítható, nem lötyög, a notch/home-sáv alá is kiterjed. */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
};

/** AUTÓ ÁLLAPOTFOTÓK - publikus bekérő oldal (bejelentkezés nélkül, tokenes
 * link, lásd middleware PUBLIC_PATHS és backend routes/auto_allapot.py). */
export default async function AutoAllapotBekeresOldal({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <AllapotFeltoltes token={token} />;
}
