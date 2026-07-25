"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Egy projekt TELJES részletnézete felugró ablakban, teljes oldalra navigálás
 * helyett - a listás/naptár nézetből nyílik (lásd ProjektekContent.tsx,
 * NaptarDiszpoContent.tsx).
 *
 * A tartalmat iframe-ben, a /embed/projektek/[id] útvonalról töltjük be, nem
 * kliens oldalon újraépítve: a részletnézet szerver komponens, ~14 párhuzamos,
 * sütire támaszkodó lekéréssel és egy csomó szerver-oldalon összeállított
 * widgettel (lásd ProjectDetailContent.tsx). Kliensbe portolva ezt mind újra
 * kellene implementálni, és a két nézet előbb-utóbb elcsúszna egymástól -
 * így viszont szó szerint UGYANAZ a nézet jelenik meg, minden művelettel
 * együtt, egyetlen forrásból. */
export function ProjectDetailModal({
  projectId,
  onClose,
}: {
  projectId: number | null;
  onClose: () => void;
}) {
  const router = useRouter();

  // Escape-re záródjon, és amíg nyitva van, a háttér ne görgethessen.
  useEffect(() => {
    if (projectId === null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [projectId, onClose]);

  if (projectId === null) return null;

  /** Bezáráskor frissítjük a mögöttes listát: a felugró ablakban végzett
   * szerkesztés (állapot, dátum, törlés) egyébként csak az iframe-en belül
   * látszódna, a mögötte lévő táblázat/naptár a régi adatot mutatná. */
  function close() {
    router.refresh();
    onClose();
  }

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 p-4" onClick={close}>
      <div
        role="dialog"
        aria-modal="true"
        className="flex h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-[var(--radius-lg)] border border-border bg-surface-1 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-4 py-2.5">
          <span className="text-[13px] text-text-secondary">Projekt részletei</span>
          <div className="flex items-center gap-2">
            <a
              href={`/projektek/${projectId}`}
              className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[12px] text-text-secondary transition-colors hover:bg-bg-accent hover:text-text-accent hover:shadow-[0_0_0_1px_var(--accent-solid)]"
            >
              Megnyitás új oldalon →
            </a>
            <button
              type="button"
              onClick={close}
              className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[12px] text-text-secondary transition-colors hover:bg-bg-accent hover:text-text-accent hover:shadow-[0_0_0_1px_var(--accent-solid)]"
            >
              Bezárás
            </button>
          </div>
        </div>
        <iframe
          key={projectId}
          src={`/embed/projektek/${projectId}`}
          title="Projekt részletei"
          className="min-h-0 flex-1 border-0 bg-background"
        />
      </div>
    </div>
  );
}
