"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type PageOption = { href: string; label: string };

/** Egy munkatárs jelszavának beállítása + oldal-hozzáférésének szerkesztése -
 * egyénenként állítható, csak admin mentheti. A munkatárs saját maga nem
 * módosíthatja (a backend /user-access/{id} PUT admin-only, lásd require_roles). */
export function UserAccessManager({
  employeeId,
  employeeLabel,
  pages,
  initialEmail,
  initialAllowedPages,
}: {
  employeeId: number;
  employeeLabel: string;
  pages: PageOption[];
  initialEmail: string | null;
  initialAllowedPages: string[] | null;
}) {
  const router = useRouter();
  const [email, setEmail] = useState(initialEmail ?? "");
  const [emailBusy, setEmailBusy] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);

  const [showAllPages, setShowAllPages] = useState(!initialAllowedPages || initialAllowedPages.length === 0);
  const [selectedPages, setSelectedPages] = useState<Set<string>>(
    new Set(initialAllowedPages && initialAllowedPages.length > 0 ? initialAllowedPages : pages.map((p) => p.href)),
  );
  const [accessBusy, setAccessBusy] = useState(false);

  function togglePage(href: string) {
    setSelectedPages((prev) => {
      const next = new Set(prev);
      if (next.has(href)) next.delete(href);
      else next.add(href);
      return next;
    });
  }

  async function saveEmail() {
    setEmailBusy(true);
    try {
      const res = await authFetch(`/api/v1/crew/${employeeId}`, { method: "PATCH", body: JSON.stringify({ email: email.trim() || null }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setEmailBusy(false);
    }
  }

  async function setPasswordSubmit() {
    if (password.length < 6) {
      alert("A jelszónak legalább 6 karakter hosszúnak kell lennie.");
      return;
    }
    setPasswordBusy(true);
    try {
      const res = await authFetch(`/api/v1/crew/${employeeId}/set-password`, { method: "POST", body: JSON.stringify({ password }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      setPassword("");
      alert("Jelszó beállítva.");
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setPasswordBusy(false);
    }
  }

  async function saveAccess() {
    setAccessBusy(true);
    try {
      const body = { allowed_pages: showAllPages ? null : Array.from(selectedPages) };
      const res = await authFetch(`/api/v1/user-access/${employeeId}`, { method: "PUT", body: JSON.stringify(body) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setAccessBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-2 text-[13px] font-medium text-text-primary">Felhasználónév (email)</p>
        <div className="flex items-center gap-2">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="pl. nev@hype.hu"
            className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
          />
          <button
            type="button"
            disabled={emailBusy || email.trim() === (initialEmail ?? "")}
            onClick={saveEmail}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            Mentés
          </button>
        </div>
      </div>

      <div className="border-t border-border pt-4">
        <p className="mb-2 text-[13px] font-medium text-text-primary">Jelszó beállítása</p>
        <div className="flex items-center gap-2">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Új jelszó (min. 6 karakter)"
            className="rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
          />
          <button
            type="button"
            disabled={passwordBusy || password.length < 6}
            onClick={setPasswordSubmit}
            className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
          >
            Jelszó beállítása
          </button>
        </div>
      </div>

      <div className="border-t border-border pt-4">
        <p className="mb-2 text-[13px] font-medium text-text-primary">Oldal-hozzáférés</p>
        <label className="mb-3 flex items-center gap-2 text-[13px] text-text-secondary">
          <input type="checkbox" checked={showAllPages} onChange={(e) => setShowAllPages(e.target.checked)} />
          Minden oldalt lát (nincs szűrés)
        </label>
        {!showAllPages && (
          <>
            <div className="mb-2 flex gap-2">
              <button type="button" onClick={() => setSelectedPages(new Set())} className="text-[12px] text-text-accent hover:underline">
                Összes kikapcsolása
              </button>
              <span className="text-text-muted">·</span>
              <button
                type="button"
                onClick={() => setSelectedPages(new Set(pages.map((p) => p.href)))}
                className="text-[12px] text-text-accent hover:underline"
              >
                Összes bekapcsolása
              </button>
            </div>
            <div className="mb-3 grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
              {pages.map((p) => (
                <label key={p.href} className="flex items-center gap-1.5 text-[12px] text-text-secondary">
                  <input type="checkbox" checked={selectedPages.has(p.href)} onChange={() => togglePage(p.href)} />
                  {p.label}
                </label>
              ))}
            </div>
          </>
        )}
        <button
          type="button"
          disabled={accessBusy}
          onClick={saveAccess}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
        >
          Mentés
        </button>
      </div>
    </div>
  );
}
