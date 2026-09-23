"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Maximize2, Sparkles, X } from "lucide-react";
import { AiAssistantChat } from "@/components/AiAssistantChat";
import { navGroups } from "@/lib/nav";

/** Az aktuális oldal neve a menüből (a leghosszabb egyező útvonal). */
function oldalNeve(utvonal: string): string | undefined {
  let legjobb: { href: string; label: string } | undefined;
  for (const g of navGroups) {
    for (const i of g.items) {
      if ((utvonal === i.href || utvonal.startsWith(i.href + "/")) && (!legjobb || i.href.length > legjobb.href.length)) {
        legjobb = { href: i.href, label: i.label };
      }
    }
  }
  return legjobb?.label;
}

/** AZ AI ASSZISZTENS MINDENHOL (a felhasználó kérése): a fejlécben, a kereső
 * mellett egy gomb, ami jobb oldali panelben nyitja meg ugyanazt az
 * asszisztenst, mint az /ai-assistant oldal - oldalváltás nélkül, az éppen
 * nyitott oldallal mint kontextussal („ez"/„ennél" erre mutat). A panel az
 * első megnyitás után csak elrejtődik (nem szűnik meg), így a folyamatban
 * lévő beszélgetés bezárás és újranyitás után is megmarad. Esc zárja. */
export function AiAssistantGomb() {
  const utvonal = usePathname();
  const [nyitva, setNyitva] = useState(false);
  const [betoltve, setBetoltve] = useState(false);
  const kontextus = useMemo(() => ({ utvonal, cim: oldalNeve(utvonal) }), [utvonal]);

  useEffect(() => {
    if (!nyitva) return;
    function billentyu(e: KeyboardEvent) {
      if (e.key === "Escape") setNyitva(false);
    }
    document.addEventListener("keydown", billentyu);
    return () => document.removeEventListener("keydown", billentyu);
  }, [nyitva]);

  // A saját oldalán nincs értelme a panelnek.
  if (utvonal === "/ai-assistant") return null;

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setBetoltve(true);
          setNyitva((v) => !v);
        }}
        aria-expanded={nyitva}
        aria-label="AI Assistant"
        title="AI Assistant — kérdezz bármit"
        className={`flex h-9 items-center gap-1.5 rounded-[var(--radius)] border px-2.5 text-[13px] transition-colors ${
          nyitva
            ? "border-text-accent bg-bg-accent text-text-accent"
            : "border-border bg-surface-2 text-text-secondary hover:bg-surface-3 hover:text-text-primary"
        }`}
      >
        <Sparkles size={15} />
        <span className="hidden lg:inline">AI</span>
      </button>

      {/* A panel a <body>-ba kerül (portál): a fejléc transform-gpu rétege a
          `fixed` elemet különben a fejléc dobozához kötné, nem a képernyőhöz. */}
      {betoltve &&
        createPortal(
        <div
          role="dialog"
          aria-label="AI Assistant"
          aria-hidden={!nyitva}
          className={`fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-border bg-surface-1 shadow-2xl transition-transform duration-200 sm:w-[480px] ${
            nyitva ? "translate-x-0" : "pointer-events-none translate-x-full"
          }`}
        >
          <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
            <p className="flex items-center gap-2 text-[14px] font-medium text-text-primary">
              <Sparkles size={15} className="text-text-accent" /> AI Assistant
            </p>
            <div className="flex items-center gap-1">
              <Link
                href="/ai-assistant"
                onClick={() => setNyitva(false)}
                title="Megnyitás teljes oldalon"
                className="rounded-[var(--radius)] p-1.5 text-text-muted hover:bg-surface-3 hover:text-text-primary"
              >
                <Maximize2 size={15} />
              </Link>
              <button
                type="button"
                onClick={() => setNyitva(false)}
                aria-label="Bezárás"
                className="rounded-[var(--radius)] p-1.5 text-text-muted hover:bg-surface-3 hover:text-text-primary"
              >
                <X size={16} />
              </button>
            </div>
          </div>
          <div className="flex min-h-0 flex-1 flex-col p-3">
            <Suspense fallback={<p className="text-[13px] text-text-muted">Betöltés…</p>}>
              <AiAssistantChat kompakt oldalKontextus={kontextus} />
            </Suspense>
          </div>
        </div>,
          document.body,
        )}
    </>
  );
}
