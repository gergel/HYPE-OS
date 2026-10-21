import { OldalVaz } from "@/components/OldalVaz";

/** Ez a fájl a Next.js-nek szól: az alkalmazás MINDEN oldalára Suspense-határt
 * tesz, és amíg a szerver az adatokat szedi össze, ezt mutatja.
 *
 * Enélkül egy menüpontra kattintva semmi nem történt a képernyőn, amíg a
 * teljes oldal el nem készült - a régi tartalom állt ott mozdulatlanul. Egy
 * lassabb lista (több száz sor) ilyenkor úgy néz ki, mintha a rendszer
 * lefagyott volna. Mostantól azonnal látszik, hogy dolgozunk rajta, és a
 * tartalom akkor váltja fel a vázat, amikor kész. */
export default function Loading() {
  return <OldalVaz />;
}
