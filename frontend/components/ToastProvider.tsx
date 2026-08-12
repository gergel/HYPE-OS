"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AlertCircle, X } from "lucide-react";

type Toast = { id: number; message: string };

const ToastContext = createContext<((message: string) => void) | null>(null);

const AUTO_DISMISS_MS = 6000;

/** Az oldal stílusához illő, nem-blokkoló értesítés-sáv a natív
 * `window.alert()` helyett (ami minden böngészőben egy csúnya, az oldal
 * témájától teljesen független rendszer-dobozt nyit, és leblokkolja a
 * JS-szálat, amíg be nem zárja a felhasználó). Mivel az `alert()` hívásoknak
 * nincs visszatérési értékük, amire a hívó kód építene, biztonságosan
 * felülírható globálisan (window.alert = ...) - így a kódbázisban szétszórt
 * ~120 meglévő `alert(...)` hívást NEM kellett egyenként átírni, mindegyik
 * automatikusan ezen a stíluson keresztül jelenik meg. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(0);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const showToast = useCallback(
    (message: string) => {
      const id = nextId.current++;
      setToasts((prev) => [...prev, { id, message }]);
      const timer = setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
      timers.current.set(id, timer);
    },
    [dismiss],
  );

  useEffect(() => {
    const original = window.alert;
    window.alert = (message?: unknown) => showToast(message === undefined ? "" : String(message));
    return () => {
      window.alert = original;
    };
  }, [showToast]);

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      {/* Az értesítés a legfelső réteg: egy modálból vagy megerősítő ablakból
          jövő visszajelzés ("Sikertelen törlés…") ne tűnjön el alattuk.
          Réteg-sorrend: modál (120) < panel (200) < kérdés (300) < értesítés. */}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[310] flex flex-col items-center gap-2 px-4">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="alert"
            className="pointer-events-auto flex w-full max-w-md items-start gap-2.5 rounded-[var(--radius-lg)] border border-text-danger/40 bg-surface-2 px-4 py-3 text-[13px] text-text-primary shadow-xl"
          >
            <AlertCircle size={16} className="mt-0.5 shrink-0 text-text-danger" />
            <p className="flex-1 whitespace-pre-line">{t.message}</p>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="shrink-0 text-text-muted hover:text-text-primary"
              aria-label="Bezárás"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/** A ToastProvider window.alert-felülírása miatt a legtöbb helyen nem is kell
 * ezt a hookot közvetlenül használni - marad meg elérhetőnek, ha valahol
 * explicit, típusos hívás kényelmesebb, mint a globális `alert(...)`. */
export function useToast(): (message: string) => void {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast csak ToastProvider-en belül használható.");
  return ctx;
}
