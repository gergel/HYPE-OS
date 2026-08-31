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

  if (hiba) {
    return (
      <main className="mx-auto max-w-xl px-6 py-20 text-center">
        <h1 className="mb-2 text-[20px] font-semibold">A megosztó link nem él</h1>
        <p className="text-[14px] opacity-70">{hiba}</p>
      </main>
    );
  }
  if (!project) {
    return <main className="mx-auto max-w-xl px-6 py-20 text-center text-[14px] opacity-70">Betöltés…</main>;
  }
  return <PortalView project={project} />;
}
