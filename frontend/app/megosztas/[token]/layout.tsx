import type { Metadata } from "next";
import { sajatAlapUrl } from "@/lib/sajatAlapUrl";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** OG/link-előnézet a MEGOSZTÓ linkekhez (a felhasználó kérése): a
 * Messengerben eddig minden megosztott link előnézete ugyanúgy nézett ki -
 * mostantól a cím megmondja, mi található a linken (a portál címe + a
 * megosztott mappa/videó neve, lásd backend portal_public.megosztas). */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  let cim: string | null = null;
  let brand = "hype";
  let boritokep: string | null = null;
  try {
    const res = await fetch(`${API}/api/v1/public/portal/megosztas/${token}`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      const t = data?.project?.title;
      if (typeof t === "string" && t.trim()) cim = t.trim();
      if (data?.project?.brand) brand = data.project.brand;
      // A portál BORÍTÓKÉPE az előnézetbe (a felhasználó kérése) - ha nincs,
      // lent a márka szerinti alap háttér megy.
      const kep = data?.project?.cover_image_url;
      if (typeof kep === "string" && kep.trim()) boritokep = kep.trim();
    }
  } catch {
    // marad az alapértelmezett
  }
  const isContentBee = brand === "contentbee";
  const name = isContentBee ? "ContentBee" : "HYPE Productions";
  const title = cim ? `${cim} — ${name}` : `${name} — Megosztott tartalom`;
  const description = cim
    ? `${cim} – megosztott videók/képek megtekintése a ${name} felületén.`
    : `Megosztott tartalom a ${name} felületén.`;
  const kepUrl =
    boritokep ?? `${await sajatAlapUrl()}${isContentBee ? "/contentbee-desktop.png" : "/default-cover-desktop.png"}`;
  return { title, description, openGraph: { title, description, images: [{ url: kepUrl }] } };
}

export default function MegosztasLayout({ children }: { children: React.ReactNode }) {
  return children;
}
