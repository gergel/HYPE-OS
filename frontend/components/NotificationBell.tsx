"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { NotificationItem } from "@/lib/api";

function formatRelative(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return "most";
  if (minutes < 60) return `${minutes} perce`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} órája`;
  const days = Math.round(hours / 24);
  return `${days} napja`;
}

/** Az @-taggelésekről és kiosztásokról (Utómunka Assigned To, Feladat felelős)
 * szóló értesítéseket mutatja a TopBar-on - lásd services/notifications.py. */
export function NotificationBell({ initial }: { initial: NotificationItem[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const unreadCount = initial.filter((n) => !n.is_read).length;

  async function markAllRead() {
    setBusy(true);
    try {
      await authFetch("/api/v1/notifications/read-all", { method: "POST" });
      router.refresh();
    } finally {
      setBusy(false);
    }
  }

  async function handleClick(n: NotificationItem) {
    setOpen(false);
    // Az olvasottá jelölést megvárjuk navigáció ELŐTT - egy router.refresh()
    // a push után versenyhelyzetbe kerülne a folyamatban lévő navigációval és
    // visszasodorná az oldalt (a céloldal saját TopBar-ja úgyis friss listát
    // kér le, nincs szükség külön refresh-re itt).
    if (!n.is_read) {
      await authFetch(`/api/v1/notifications/${n.id}/read`, { method: "POST" });
    }
    router.push(n.link);
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="Értesítések"
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-full border border-border p-2 text-text-secondary hover:bg-surface-3"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-bg-danger px-1 text-[10px] font-medium text-text-danger">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-20 mt-2 w-80 rounded-[var(--radius)] border border-border bg-surface-2 shadow-lg">
          <div className="flex items-center justify-between border-b border-border px-3 py-2">
            <p className="text-[13px] font-medium text-text-primary">Értesítések</p>
            {unreadCount > 0 && (
              <button
                type="button"
                disabled={busy}
                onClick={markAllRead}
                className="text-[12px] text-text-accent hover:underline disabled:opacity-50"
              >
                Mind olvasott
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {initial.length === 0 && <p className="px-3 py-4 text-[13px] text-text-muted">Nincs értesítésed.</p>}
            {initial.map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={() => handleClick(n)}
                className={`block w-full border-b border-border px-3 py-2.5 text-left last:border-b-0 hover:bg-surface-3 ${
                  n.is_read ? "" : "bg-bg-accent"
                }`}
              >
                <p className="text-[13px] text-text-primary">{n.message}</p>
                <p className="mt-0.5 text-[11px] text-text-muted">{formatRelative(n.created_at)}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
