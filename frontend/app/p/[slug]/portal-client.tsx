"use client";
import { Suspense, useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { getPublicProject, getByShare, PublicPortal } from "@/lib/portalApi";
import { PortalView } from "@/components/media-portal/portal-view";
import { PasswordGate } from "@/components/media-portal/password-gate";
import { BarionPixel } from "@/components/media-portal/BarionPixel";
import { CookieConsent } from "@/components/media-portal/CookieConsent";
import { pixelPurchase } from "@/lib/barionPixel";

export default function PortalClient() {
  return (
    <div className="hype-portal dark grain min-h-screen bg-ink text-bone">
      {/* A Barion Pixel és a süti-sáv csak itt, az ügyfeleknek szóló portálon
          fut - a belső HYPE OS oldalakon nincs követés. */}
      <BarionPixel />
      <Suspense
        fallback={
          <main className="flex min-h-screen items-center justify-center">
            <span className="font-mono text-xs uppercase tracking-eyebrow text-mist">Portál betöltése…</span>
          </main>
        }
      >
        <PortalContent />
      </Suspense>
      <CookieConsent />
    </div>
  );
}

function PortalContent() {
  const params = useParams();
  const search = useSearchParams();
  const slug = params.slug as string;
  const shareToken = search.get("share");
  const [project, setProject] = useState<PublicPortal | null>(null);
  // Sikeres fizetés utáni visszatérés: a backend a visszairányításba teszi,
  // mit vettek (?paid=1&pkg=&amt=&pid=) - ebből megy a Barion Pixel purchase
  // eseménye. A paramétereket utána kitöröljük az URL-ből, hogy egy frissítés
  // ne küldje el még egyszer.
  useEffect(() => {
    if (search.get("paid") !== "1") return;
    const pkg = search.get("pkg") || "";
    const osszeg = parseInt(search.get("amt") || "0", 10) || 0;
    const cimkek: Record<string, string> = { "1month": "1 hónap", "180days": "180 nap", "1year": "1 év" };
    pixelPurchase(pkg, cimkek[pkg] || "Tárhely-hosszabbítás", osszeg, search.get("pid") || "");
    try {
      const url = new URL(window.location.href);
      ["paid", "pkg", "amt", "pid"].forEach((k) => url.searchParams.delete(k));
      window.history.replaceState({}, "", url.pathname + url.search);
    } catch {
      /* a takarítás elmaradása nem baj: legfeljebb ott marad a query string */
    }
  }, [search]);

  const [locked, setLocked] = useState(false);
  const [lockMeta, setLockMeta] = useState<{ title?: string; cover?: string }>({});
  const [expired, setExpired] = useState<{
    title: string;
    brand: string;
    contact_email: string;
    payment_mode: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load(unlockToken?: string) {
    setLoading(true);
    try {
      if (shareToken) {
        const data = await getByShare(shareToken);
        if (data.expired) {
          setExpired({
            title: data.title || "",
            brand: data.brand || "hype",
            contact_email: data.contact_email || "info@hypestab.hu",
            payment_mode: data.payment_mode || "contact",
          });
          setLocked(false);
          setProject(null);
        } else if (data.project) {
          setProject(data.project);
          setLocked(false);
          setExpired(null);
        }
      } else {
        const stored = unlockToken || sessionStorage.getItem(`hype_unlock_${slug}`) || undefined;
        const data = await getPublicProject(slug, stored);
        if (data.expired) {
          setExpired({
            title: data.title || "",
            brand: data.brand || "hype",
            contact_email: data.contact_email || "info@hypestab.hu",
            payment_mode: data.payment_mode || "contact",
          });
          setLocked(false);
          setProject(null);
        } else if (data.locked) {
          setLocked(true);
          setLockMeta({ title: data.title, cover: data.cover_image_url });
          setExpired(null);
        } else if (data.project) {
          setProject(data.project);
          setLocked(false);
          setExpired(null);
        }
      }
    } catch {
      setError("Ez a portál nem található.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug, shareToken]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <span className="font-mono text-xs uppercase tracking-eyebrow text-mist">Portál betöltése…</span>
      </main>
    );
  }
  if (error) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center">
        <h1 className="font-display text-3xl text-bone">A portál nem található</h1>
        <p className="text-mist">{error}</p>
      </main>
    );
  }
  if (locked) {
    return <PasswordGate slug={slug} title={lockMeta.title} cover={lockMeta.cover} onUnlock={(t) => load(t)} />;
  }

  if (expired) {
    const minimalProject: PublicPortal = {
      slug,
      expires_at: null,
      payment_mode: "contact",
      title: expired.title,
      client_name: "",
      description: "",
      cover_image_url: "",
      brand: expired.brand,
      project_date: "",
      videos: [],
      folders: [],
      images: [],
    };
    return (
      <PortalView
        project={minimalProject}
        expiredContactEmail={expired.contact_email}
        expiredPaymentMode={expired.payment_mode}
      />
    );
  }

  return project ? <PortalView project={project} /> : null;
}
