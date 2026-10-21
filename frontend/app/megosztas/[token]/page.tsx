"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getMegosztas, type PublicPortal } from "@/lib/portalApi";
import { PortalView } from "@/components/media-portal/portal-view";

/** EGY MAPPA vagy EGY VIDEÓ megosztott nézete (a felhasználó kérése).
 *
 * A link birtokosa csak a megosztott részt látja - a portál többi mappája és
 * videója nem érhető el ezen a tokenen (a szerver eleve csak a szűkített
 * tartalmat adja ki, lásd backend portal_public.megosztas). A megjelenítés
 * ugyanaz a PortalView, mint a teljes ügyfél-portálon - egy forrásból. */
export default function MegosztasPage() {
  const params = useParams<{ token: string }>();
  const [project, setProject] = useState<PublicPortal | null>(null);
  const [hiba, setHiba] = useState<string | null>(null);

  useEffect(() => {
    getMegosztas(params.token)
      .then((v) => setProject(v.project))
      .catch((e) => setHiba(String(e?.message ?? e)));
  }, [params.token]);

  // UGYANAZ a sötét portál-téma burkolja, mint a /p/{slug} ügyfél-nézetet
  // (hype-portal + dark + bg-ink) - enélkül az oldal a belső app alap-témája
  // alatt futott, és a színek "invertálódtak" (a felhasználó hibajelzése).
  return (
    <div className="hype-portal dark grain min-h-screen bg-ink text-bone">
      {hiba ? (
        <main className="flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center">
          <h1 className="font-display text-3xl text-bone">A megosztó link nem él</h1>
          <p className="text-mist">{hiba}</p>
        </main>
      ) : !project ? (
        <main className="flex min-h-screen items-center justify-center">
          <span className="font-mono text-xs uppercase tracking-eyebrow text-mist">Betöltés…</span>
        </main>
      ) : (
        <PortalView project={project} />
      )}
    </div>
  );
}
