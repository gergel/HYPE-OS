"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Undo2 } from "lucide-react";
import { kovetkezoVisszavonas } from "@/lib/visszavonas";

/** Rendszerszintű Ctrl+Z / Cmd+Z - a gyökér-layoutban ül, így minden oldalon
 * él. A verembe az authFetch teszi a bejegyzéseket (mező-mentések előző
 * értéke, törlés-pillanatképek - lásd lib/authFetch.ts, lib/visszavonas.ts).
 *
 * Gépelés közben (input/textarea/szerkeszthető mező) NEM nyúlunk a
 * billentyűhöz: ott a böngésző saját szöveg-visszavonása a helyes viselkedés,
 * a miénk csak a már ELMENTETT módosításokat és törléseket vonja vissza. */
export function VisszavonasFigyelo() {
  const router = useRouter();
  const [uzenet, setUzenet] = useState<string | null>(null);
  const [hiba, setHiba] = useState(false);
  const idozito = useRef<number | null>(null);
  const fut = useRef(false);

  useEffect(() => {
    const kezelo = async (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== "z" || (!e.ctrlKey && !e.metaKey) || e.shiftKey || e.altKey) return;
      const cel = e.target as HTMLElement | null;
      const tag = cel?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select" || cel?.isContentEditable) return;
      if (fut.current) return; // egyszerre egy visszavonás fusson
      const bejegyzes = kovetkezoVisszavonas();
      if (!bejegyzes) return;
      e.preventDefault();
      fut.current = true;
      let ok = false;
      try {
        ok = await bejegyzes.futtat();
      } catch {
        ok = false;
      } finally {
        fut.current = false;
      }
      setHiba(!ok);
      setUzenet(ok ? bejegyzes.cimke : "A visszavonás nem sikerült (lehet, hogy közben más módosította).");
      if (ok) router.refresh();
      if (idozito.current !== null) window.clearTimeout(idozito.current);
      idozito.current = window.setTimeout(() => setUzenet(null), 4000);
    };
    window.addEventListener("keydown", kezelo);
    return () => {
      window.removeEventListener("keydown", kezelo);
      if (idozito.current !== null) window.clearTimeout(idozito.current);
    };
  }, [router]);

  if (!uzenet) return null;
  return (
    <div
      role="status"
      className={`fixed bottom-5 left-1/2 z-[300] flex -translate-x-1/2 items-center gap-2 rounded-[var(--radius)] border px-4 py-2.5 text-[13px] shadow-lg ${
        hiba
          ? "border-[color:var(--text-danger)]/40 bg-bg-danger text-text-danger"
          : "border-border-strong bg-surface-1 text-text-primary"
      }`}
    >
      <Undo2 size={15} aria-hidden />
      {uzenet}
    </div>
  );
}
