import type { Metadata } from "next";
import { sajatAlapUrl } from "@/lib/sajatAlapUrl";
import PortalClient from "./portal-client";

// Env nélkül (fejlesztői környezet) a lokális backend - élesben a
// NEXT_PUBLIC_API_URL van beállítva (ugyanaz a minta, mint a többi publikus
// oldalon).
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  let brand = "hype";
  // A PORTÁL CÍME az előnézetbe (a felhasználó kérése): a Messengerben/
  // linkelőnézetben eddig minden portál ugyanúgy nézett ki - mostantól a
  // cím megmondja, MI található az adott portálon. Zárolt/lejárt portálnál
  // is megvan (a title ott a válasz tetején jön).
  let portalCim: string | null = null;
  let boritokep: string | null = null;
  try {
    const res = await fetch(`${API}/api/v1/public/portal/${slug}`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      const b = data?.project?.brand || data?.brand;
      if (b) brand = b;
      const cim = data?.project?.title || data?.title;
      if (typeof cim === "string" && cim.trim()) portalCim = cim.trim();
      // A portál BORÍTÓKÉPE (a felhasználó kérése): ha be van állítva, a
      // link-előnézet is azt mutatja - zárolt portálnál is jön a válaszban.
      const kep = data?.project?.cover_image_url || data?.cover_image_url;
      if (typeof kep === "string" && kep.trim()) boritokep = kep.trim();
    }
  } catch {
    // ha nem sikerül, marad a hype alapértelmezett
  }

  const isContentBee = brand === "contentbee";
  const name = isContentBee ? "ContentBee" : "HYPE Productions";
  const title = portalCim ? `${portalCim} — ${name}` : `${name} — Client Cloud`;
  const description = portalCim
    ? `${portalCim} – videók és képek megtekintése a ${name} Client Cloud felületén.`
    : `Privát felhő megosztás ${name} ügyfeleknek.`;
  // Borítókép híján az AKTUÁLIS alap háttér megy az előnézetbe - ugyanaz,
  // amit a portál hero-ja is mutat (lásd portal-view.tsx defaultCoverDesktop).
  const kepUrl =
    boritokep ?? `${await sajatAlapUrl()}${isContentBee ? "/contentbee-desktop.png" : "/default-cover-desktop.png"}`;

  return {
    title,
    description,
    openGraph: { title, description, images: [{ url: kepUrl }] },
  };
}

export default function PortalPage() {
  return <PortalClient />;
}
