import type { Metadata } from "next";
import PortalClient from "./portal-client";

const API = process.env.NEXT_PUBLIC_API_URL || "";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  let brand = "hype";
  try {
    const res = await fetch(`${API}/api/v1/public/portal/${slug}`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      const b = data?.project?.brand || data?.brand;
      if (b) brand = b;
    }
  } catch {
    // ha nem sikerül, marad a hype alapértelmezett
  }

  const isContentBee = brand === "contentbee";
  const name = isContentBee ? "ContentBee" : "HYPE Productions";
  const title = `${name} — Client Cloud`;
  const description = `Privát felhő megosztás ${name} ügyfeleknek.`;

  return {
    title,
    description,
    openGraph: { title, description },
  };
}

export default function PortalPage() {
  return <PortalClient />;
}
