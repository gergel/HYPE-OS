"use client";

import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { usePathname } from "next/navigation";
import { Logo } from "@/components/Logo";
import { NavList } from "@/components/NavList";

/** A TELEFONOS navigáció: az asztali oldalsáv (Sidebar) `md` alatt teljesen
 * eltűnik, e nélkül a komponens nélkül a rendszer telefonon navigálhatatlan
 * lenne - csak a hamburger-gombbal nyíló fiók pótolja.
 *
 * A TopBar tölti be, mert az van minden oldalon (a Sidebar-t hordozó
 * (app)/layout.tsx-et minden oldal a saját <TopBar />-jával kezdi) - így a
 * gomb minden oldalon ugyanott, a fejléc bal szélén jelenik meg, anélkül,
 * hogy mind az ötven oldalnak külön át kellene adnia a jogosultság-adatokat. */
export function MobileNav({
  allowedPages,
  pagePermissions,
  anyagKorlat,
}: {
  allowedPages: string[] | null;
  pagePermissions: Record<string, string[]> | null;
  anyagKorlat: number[] | null;
}) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // A fiókot a `<body>` VÉGÉRE portálozzuk (lásd ModalReteg.tsx ugyanerről a
  // jelenségről): a TopBar, amiben ez a gomb áll, `backdrop-blur-xl`-t
  // használ, ami új "containing block"-ot nyit a `position: fixed`
  // gyerekeinek - enélkül a fiók nem a képernyőhöz, hanem a fejléc
  // sávjához igazodna, és egy alacsony, összenyomott sávvá zsugorodna a
  // teteje helyett a teljes magasság helyett.
  const [mount, setMount] = useState(false);
  useEffect(() => setMount(true), []);

  // Navigáció után a fiók magától becsukódik - anélkül a következő lapon is
  // nyitva maradna, eltakarva a tartalmat.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Amíg a fiók nyitva van, a mögötte lévő oldal ne görgethessen - telefonon
  // enélkül a háttér-tartalom görgetése "átüt" a fiókon keresztül.
  useEffect(() => {
    if (!open) return;
    const eredeti = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = eredeti;
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Menü megnyitása"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--radius)] border border-border text-text-secondary hover:bg-surface-3 md:hidden"
      >
        <Menu size={18} strokeWidth={1.75} aria-hidden />
      </button>

      {open &&
        mount &&
        createPortal(
          <div className="fixed inset-0 z-50 md:hidden">
            <div
              aria-hidden
              onClick={() => setOpen(false)}
              className="fade-in absolute inset-0 bg-black/60 backdrop-blur-[1px]"
            />
            <div className="absolute inset-y-0 left-0 flex w-[280px] max-w-[85vw] flex-col border-r border-border bg-surface-1 px-3 py-6 shadow-xl">
              <div className="mb-8 flex items-center justify-between px-3">
                <Logo />
                <button
                  type="button"
                  onClick={() => setOpen(false)}
                  aria-label="Menü bezárása"
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius)] text-text-muted hover:bg-surface-3"
                >
                  <X size={18} strokeWidth={1.75} aria-hidden />
                </button>
              </div>
              <NavList
                allowedPages={allowedPages}
                pagePermissions={pagePermissions}
                anyagKorlat={anyagKorlat}
                onNavigate={() => setOpen(false)}
              />
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
