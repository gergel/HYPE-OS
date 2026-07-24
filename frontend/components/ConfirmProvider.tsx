"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";

type PendingConfirm = { message: string; resolve: (value: boolean) => void };

const ConfirmContext = createContext<((message: string) => Promise<boolean>) | null>(null);

/** Az oldal stílusához illő megerősítő párbeszédablak a natív
 * `window.confirm()` helyett. A natív confirm() szinkron (visszaadja a
 * választ azonnal, blokkolva a JS-szálat) - egy React modal viszont
 * szükségszerűen aszinkron, ezért ezt (szemben a ToastProvider alert()
 * felülírásával) NEM lehetett globálisan, hívóhelyek módosítása nélkül
 * megoldani: minden `if (!confirm("...")) return;` hívóhelyet át kellett
 * írni `if (!(await confirm("..."))) return;`-re, ezzel a hookkal. */
export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<PendingConfirm | null>(null);
  const resolveRef = useRef<((value: boolean) => void) | null>(null);

  const confirm = useCallback((message: string): Promise<boolean> => {
    return new Promise<boolean>((resolve) => {
      resolveRef.current = resolve;
      setPending({ message, resolve });
    });
  }, []);

  function respond(value: boolean) {
    resolveRef.current?.(value);
    resolveRef.current = null;
    setPending(null);
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {pending && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 px-6"
          onClick={() => respond(false)}
        >
          <div
            role="alertdialog"
            aria-modal="true"
            className="w-full max-w-sm rounded-[var(--radius-lg)] border border-border bg-surface-2 p-5 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="mb-5 whitespace-pre-line text-[13px] text-text-primary">{pending.message}</p>
            <div className="flex justify-end gap-2.5">
              <button
                type="button"
                autoFocus
                onClick={() => respond(false)}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
              >
                Mégse
              </button>
              <button
                type="button"
                onClick={() => respond(true)}
                className="rounded-[var(--radius)] border border-text-danger/40 bg-bg-danger px-3 py-1.5 text-[13px] text-text-danger hover:opacity-90"
              >
                Rendben
              </button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): (message: string) => Promise<boolean> {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm csak ConfirmProvider-en belül használható.");
  return ctx;
}
