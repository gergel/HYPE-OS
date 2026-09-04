import type { Metadata } from "next";

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
  try {
    const res = await fetch(`${API}/api/v1/public/portal/megosztas/${token}`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      const t = data?.project?.title;
      if (typeof t === "string" && t.trim()) cim = t.trim();
      if (data?.project?.brand) brand = data.project.brand;
    }
  } catch {
    // marad az alapértelmezett
  }
  const name = brand === "contentbee" ? "ContentBee" : "HYPE Productions";
  const title = cim ? `${cim} — ${name}` : `${name} — Megosztott tartalom`;
  const description = cim
    ? `${cim} – megosztott videók/képek megtekintése a ${name} felületén.`
    : `Megosztott tartalom a ${name} felületén.`;
  return { title, description, openGraph: { title, description } };
}

export default function MegosztasLayout({ children }: { children: React.ReactNode }) {
  return children;
}
