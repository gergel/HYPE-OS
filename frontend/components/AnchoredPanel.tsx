"use client";

import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";

/** Legördülő panel, ami a "gazdájához" (anchor) igazodik, de a DOM-ban a
 * <body> alá kerül (portál).
 *
 * Miért nem elég egy sima `absolute top-full`: a részletnézetek kártyái CSS
 * multi-column elrendezésben vannak (lásd DetailSections `columns-2`), ahol a
 * böngésző az abszolút pozicionált elemeket a TÖRDELT oszlop-fragmentumhoz
 * viszonyítja - a legördülő tartalma emiatt átcsúszik egy másik oszlopba, az
 * oldal tetejére. Ugyanez a baj az `overflow: hidden`/görgethető szülőknél is:
 * ott levágódna a panel. Portálban, fix pozícióval mindkettő megszűnik.
 *
 * Ha alul nem fér el, felfelé nyílik; a szélessége soha nem lóg ki a
 * képernyőről. Görgetésre/átméretezésre újraszámol. */
export function AnchoredPanel({
  anchorRef,
  onClose,
  width = 288,
  children,
}: {
  anchorRef: RefObject<HTMLElement | null>;
  /** Kattintás a panelen ÉS az anchoron kívül - ilyenkor záródik. */
  onClose: () => void;
  width?: number;
  children: React.ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number; maxHeight: number } | null>(null);

  useLayoutEffect(() => {
    function place() {
      const anchor = anchorRef.current;
      if (!anchor) return;
      const rect = anchor.getBoundingClientRect();
      const margin = 8;
      const panelHeight = panelRef.current?.offsetHeight ?? 320;
      const belowRoom = window.innerHeight - rect.bottom - margin;
      const aboveRoom = rect.top - margin;
      // Lefelé nyílik, hacsak ott nem fér el ÉS fölötte több hely van.
      const openUp = belowRoom < Math.min(panelHeight, 240) && aboveRoom > belowRoom;
      const maxHeight = Math.max(160, (openUp ? aboveRoom : belowRoom) - 4);
      const top = openUp ? Math.max(margin, rect.top - Math.min(panelHeight, maxHeight) - 4) : rect.bottom + 4;
      const left = Math.min(Math.max(margin, rect.left), Math.max(margin, window.innerWidth - width - margin));
      setPos({ top, left, maxHeight });
    }
    place();
    window.addEventListener("resize", place);
    // capture: a görgetés bármelyik belső, görgethető konténerben történhet
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [anchorRef, width]);

  useEffect(() => {
    function onPointerDown(e: MouseEvent) {
      const target = e.target as Node;
      if (panelRef.current?.contains(target) || anchorRef.current?.contains(target)) return;
      // A data-panel-tars jelölésű felület (pl. a panelből nyíló
      // darabszám-kérdező ablak, lásd EquipmentBookingManager) kattintásai
      // nem számítanak "kívülre" - a panel nyitva marad, amíg ott dolgoznak.
      // A stopPropagation itt nem véd: a React a documentre delegál, így ez a
      // szintén document-szintű figyelő attól még lefutna.
      if (target instanceof Element && target.closest("[data-panel-tars]")) return;
      onClose();
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [anchorRef, onClose]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      ref={panelRef}
      // Jelölő a kívül-kattintást figyelő komponenseknek: ez a doboz a
      // `<body>` végén él, tehát DOM szerint mindig "kívül" van azon, ami
      // megnyitotta. Enélkül egy legördülőt tartalmazó felugró panel a saját
      // legördülőjére kattintva bezárul (lásd TableFilterBuilder).
      data-anchored-panel=""
      // Amíg nincs kiszámolt pozíció, láthatatlanul rendereljük - így meg
      // tudjuk mérni a magasságát anélkül, hogy rossz helyen felvillanna.
      style={{
        position: "fixed",
        top: pos?.top ?? -9999,
        left: pos?.left ?? -9999,
        width,
        maxHeight: pos?.maxHeight,
        visibility: pos ? "visible" : "hidden",
      }}
      className="z-[200] overflow-y-auto rounded-[var(--radius-lg)] border border-border bg-surface-2 p-2 shadow-xl"
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </div>,
    document.body,
  );
}
