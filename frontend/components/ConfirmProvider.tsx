"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";

type PendingConfirm = { message: string; kind: "confirm" | "alert" };

const ConfirmContext = createContext<((message: string) => Promise<boolean>) | null>(null);
/** Csak tudomásul vehető (egy gombos) felugró ablak - ugyanaz a keret, mint a
 * megerősítőnél. Olyan hibáknál kell, ahol a felhasználónak el kell olvasnia
 * egy listát (pl. kiknek hiányzik az email címe a diszpó küldése előtt), tehát
 * egy magától eltűnő értesítés-sáv (lásd ToastProvider) kevés lenne. */
const AlertContext = createContext<((message: string) => Promise<void>) | null>(null);

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
      setPending({ message, kind: "confirm" });
    });
  }, []);

  const alertDialog = useCallback((message: string): Promise<void> => {
    return new Promise<void>((resolve) => {
      resolveRef.current = () => resolve();
      setPending({ message, kind: "alert" });
    });
  }, []);

  function respond(value: boolean) {
    resolveRef.current?.(value);
    resolveRef.current = null;
    setPending(null);
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      <AlertContext.Provider value={alertDialog}>{children}</AlertContext.Provider>
      {pending && (
        <div
          className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 px-6"
          onClick={() => respond(false)}
        >
          <div
            role="alertdialog"
            aria-modal="true"
            className="w-full max-w-sm fade-in rounded-[var(--radius-lg)] border border-border-strong bg-surface-2 p-6 shadow-[0_24px_60px_-30px_rgba(0,0,0,0.95)] shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="mb-5 whitespace-pre-line text-[13px] text-text-primary">{pending.message}</p>
            <div className="flex justify-end gap-2.5">
              {pending.kind === "confirm" && (
                <button
                  type="button"
                  autoFocus
                  onClick={() => respond(false)}
                  className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
                >
                  Mégse
                </button>
              )}
              <button
                type="button"
                autoFocus={pending.kind === "alert"}
                onClick={() => respond(true)}
                className="btn btn-danger"
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

/** Egy gombos, tudomásul vehető felugró ablak (lásd AlertContext). */
export function useAlertDialog(): (message: string) => Promise<void> {
  const ctx = useContext(AlertContext);
  if (!ctx) throw new Error("useAlertDialog csak ConfirmProvider-en belül használható.");
  return ctx;
}
