"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type PageOption = { page: string; label: string };
type DbTab = { tab_key: string; label: string };

const EXTRA_ACTIONS: { key: string; label: string }[] = [
  { key: "edit", label: "Szerkesztés" },
  { key: "create", label: "Létrehozás" },
  { key: "delete", label: "Törlés" },
];
const FULL_ACCESS = ["view", "edit", "create", "delete"];

/** Egy munkatárs jelszavának beállítása + oldal-hozzáférésének szerkesztése -
 * egyénenként állítható, csak admin mentheti. A munkatárs saját maga nem
 * módosíthatja (a backend /user-access/{id} PUT admin-only, lásd require_roles).
 *
 * Egy bejelölt oldalon belül a megtekintés mindig jár (ez adja a láthatóságot,
 * lásd middleware.ts) - az edit/create/delete külön-külön kapcsolható, hogy
 * valaki csak megtekinthesse, vagy szerkeszthesse/létrehozhassa/törölhesse is
 * (lásd core/security.check_page_action a backend-oldali kikényszerítéshez). */
export function UserAccessManager({
  employeeId,
  employeeLabel,
  pages,
  initialEmail,
  initialPagePermissions,
  pageTabsMap = {},
}: {
  employeeId: number;
  employeeLabel: string;
  pages: PageOption[];
  initialEmail: string | null;
  initialPagePermissions: Record<string, string[]> | null;
  /** {oldal_href: fülek} azokhoz az oldalakhoz, amiknek van admin által
   * konfigurált fül-elrendezése (lásd DetailTabEditor) - ha egy oldal itt
   * szerepel, a bejelölése alatt fülönként külön Látja/Szerkesztheti
   * checkbox jelenik meg, ami a "{page}:{tab_key}" összetett kulcsot írja a
   * page_permissions dict-be (lásd backend core/security.check_page_action,
   * api/crud_router.py update_item). */
  pageTabsMap?: Record<string, DbTab[]>;
}) {
  const router = useRouter();
  const [email, setEmail] = useState(initialEmail ?? "");
  const [emailBusy, setEmailBusy] = useState(false);
  const [password, setPassword] = useState("");
  const [passwordBusy, setPasswordBusy] = useState(false);

  const hasRestriction = !!initialPagePermissions && Object.keys(initialPagePermissions).length > 0;
  const [showAllPages, setShowAllPages] = useState(!hasRestriction);
  const [permissions, setPermissions] = useState<Map<string, Set<string>>>(
    new Map(
      hasRestriction
        ? Object.entries(initialPagePermissions!).map(([page, actions]) => [page, new Set(actions)])
        : pages.map((p) => [p.page, new Set(FULL_ACCESS)]),
    ),
  );
  const [accessBusy, setAccessBusy] = useState(false);
  const [revokeBusy, setRevokeBusy] = useState(false);

  function togglePage(page: string) {
    setPermissions((prev) => {
      const next = new Map(prev);
      if (next.has(page)) next.delete(page);
      else next.set(page, new Set(FULL_ACCESS));
      return next;
    });
  }

  function toggleAction(page: string, action: string) {
    setPermissions((prev) => {
      const next = new Map(prev);
      const actions = new Set(next.get(page));
      if (actions.has(action)) actions.delete(action);
      else actions.add(action);
      next.set(page, actions);
      return next;
    });
  }

  /** A fülek MINDIG láthatók (lásd lib/detailTabs.tsx) - itt csak a
   * szerkeszthetőség korlátozható. A checkbox bejelölése hozza létre a
   * "{page}:{tab_key}" összetett kulcsot ["edit"] értékkel (a fül ETTŐL
   * KEZDVE csak olvasható lesz, amíg admin vissza nem kapcsolja) - kijelölés
   * hiánya = a fül öröklődik az oldal-szintű szerkesztési jogból. */
  function toggleTabEditRestriction(compositeKey: string) {
    setPermissions((prev) => {
      const next = new Map(prev);
      if (next.has(compositeKey)) next.delete(compositeKey);
      else next.set(compositeKey, new Set());
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
      const body = {
        page_permissions: showAllPages
          ? null
          : Object.fromEntries(Array.from(permissions.entries()).map(([page, actions]) => [page, Array.from(actions)])),
      };
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

  async function revokeAccess() {
    if (!confirm(`Biztosan törlöd ${employeeLabel} hozzáférését? A jelszava törlődik (nem tud többé bejelentkezni), az oldal- és mező-hozzáférése alapértelmezettre áll vissza.`)) {
      return;
    }
    setRevokeBusy(true);
    try {
      const res = await authFetch(`/api/v1/user-access/${employeeId}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setRevokeBusy(false);
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
              <button
                type="button"
                onClick={() => setPermissions(new Map())}
                className="text-[12px] text-text-accent hover:underline"
              >
                Összes kikapcsolása
              </button>
              <span className="text-text-muted">·</span>
              <button
                type="button"
                onClick={() => setPermissions(new Map(pages.map((p) => [p.page, new Set(FULL_ACCESS)])))}
                className="text-[12px] text-text-accent hover:underline"
              >
                Összes bekapcsolása (teljes joggal)
              </button>
            </div>
            <p className="mb-2 text-[12px] text-text-muted">
              A bejelölt oldalt megtekintheti - az alábbi jelölőnégyzetekkel adhatsz hozzá szerkesztési/létrehozási/törlési jogot is.
            </p>
            <div className="mb-3 grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
              {pages.map((p) => {
                const actions = permissions.get(p.page);
                const tabs = pageTabsMap[p.page];
                return (
                  <div key={p.page}>
                    <label className="flex items-center gap-1.5 text-[12px] font-medium text-text-secondary">
                      <input type="checkbox" checked={!!actions} onChange={() => togglePage(p.page)} />
                      {p.label}
                    </label>
                    {actions && (
                      <div className="ml-5 mt-0.5 flex flex-wrap gap-x-2.5 text-[11px] text-text-muted">
                        {EXTRA_ACTIONS.map((a) => (
                          <label key={a.key} className="flex items-center gap-1">
                            <input type="checkbox" checked={actions.has(a.key)} onChange={() => toggleAction(p.page, a.key)} />
                            {a.label}
                          </label>
                        ))}
                      </div>
                    )}
                    {actions && tabs && tabs.length > 0 && (
                      <div className="ml-5 mt-1.5 space-y-1 border-l border-border pl-2">
                        <p className="text-[10px] text-text-muted">
                          Fülenkénti felülbírálás (opcionális) - a fülek MINDIG láthatók, itt csak azt jelölheted be, mely fül legyen
                          KIVÉTELESEN csak olvasható a fenti oldal-szintű szerkesztési jog ellenére:
                        </p>
                        {tabs.map((tab) => {
                          const compositeKey = `${p.page}:${tab.tab_key}`;
                          const restricted = permissions.has(compositeKey);
                          return (
                            <label key={tab.tab_key} className="flex items-center gap-1 text-[11px] text-text-muted">
                              <input type="checkbox" checked={restricted} onChange={() => toggleTabEditRestriction(compositeKey)} />
                              {tab.label} (csak olvasható)
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
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

      <div className="border-t border-border pt-4">
        <button
          type="button"
          disabled={revokeBusy}
          onClick={revokeAccess}
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-danger hover:bg-surface-3 disabled:opacity-50"
        >
          Hozzáférés törlése
        </button>
      </div>
    </div>
  );
}
