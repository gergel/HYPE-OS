"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { FieldVisibilityManager } from "@/components/FieldVisibilityManager";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { SelectDropdown } from "@/components/SelectDropdown";
import { UserAccessManager } from "@/components/UserAccessManager";
import { authFetch } from "@/lib/authFetch";

type EmployeeOption = { id: number; full_name: string; email: string | null; role: string; has_password: boolean };
type PageOption = { page: string; label: string };
type FieldOption = { key: string; label: string };
type VisibilityEntity = { entityType: string; label: string; availableFields: FieldOption[] };
type PageAccessConfig = {
  employee_id: number;
  page_permissions: Record<string, string[]> | null;
  /** Ha ki van töltve, a felhasználó CSAK ezeket az utómunka-anyagokat látja. */
  lathato_deliverable_idk: number[] | null;
};
type FieldVisibilityConfig = { employee_id: number; entity_type: string; visible_fields: string[] | null };
type DbTab = { tab_key: string; label: string };

/** A szerepkörök emberi nevei. A kulcsok a backend SystemRole értékei
 * (lásd models/employee.py) - korábban itt "editor"/"client" szerepelt, ami
 * sosem létezett, ezért a Vágó/Ügyfél szerepkörnél a nyers kód látszott. */
const ROLE_LABEL: Record<string, string> = {
  admin: "Admin",
  operator: "Operatőr",
  vago: "Vágó",
  ugyfel: "Ügyfél",
  adminisztracio: "Adminisztráció",
};

const ROLE_ORDER = ["admin", "adminisztracio", "operator", "vago", "ugyfel"];

/** A szerepkör magyarázata - hogy ne kelljen kitalálni, mit ad az
 * Adminisztráció szerepkör. */
const ROLE_LEIRAS: Record<string, string> = {
  adminisztracio:
    "A projektek papírozásáért felel - a Teendőim widget felhozza neki a hiányzó belsős/külsős TIG-eket, az alvállalkozói és a megrendelői szerződéseket.",
};

/** Kereshető munkatárs-választó a Beállítások oldalon - sok (akár több száz,
 * Notionből importált) munkatárs esetén nem praktikus mindenkinek egyszerre
 * kirenderelni a jelszó/oldal/mező-hozzáférés szerkesztőjét (ez korábban DB
 * connection pool kimerüléshez is vezetett), ezért csak a kiválasztott
 * munkatársét jelenítjük meg. */
export function EmployeeAccessManager({
  employees,
  pages,
  visibilityEntities,
  pageAccessConfigs,
  anyagok = [],
  fieldVisibilityConfigs,
  pageTabsMap = {},
}: {
  employees: EmployeeOption[];
  pages: PageOption[];
  visibilityEntities: VisibilityEntity[];
  pageAccessConfigs: PageAccessConfig[];
  /** Minden utómunka-anyag - a korlátozott (külsős vágó) fiókok
   * beállításához (lásd UserAccessManager). */
  anyagok?: { id: number; projekt_neve: string }[];
  fieldVisibilityConfigs: FieldVisibilityConfig[];
  pageTabsMap?: Record<string, DbTab[]>;
}) {
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [szerepkorBusy, setSzerepkorBusy] = useState(false);
  const router = useRouter();

  async function mentSzerepkor(employeeId: number, role: string) {
    setSzerepkorBusy(true);
    try {
      const res = await authFetch(`/api/v1/crew/${employeeId}`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setSzerepkorBusy(false);
    }
  }

  const pagePermissionsByEmployee = useMemo(
    () => new Map(pageAccessConfigs.map((c) => [c.employee_id, c.page_permissions])),
    [pageAccessConfigs],
  );
  const anyagKorlatByEmployee = useMemo(
    () => new Map(pageAccessConfigs.map((c) => [c.employee_id, c.lathato_deliverable_idk])),
    [pageAccessConfigs],
  );

  const fieldVisibilityByEmployee = useMemo(() => {
    const map = new Map<number, Map<string, string[] | null>>();
    for (const config of fieldVisibilityConfigs) {
      if (!map.has(config.employee_id)) map.set(config.employee_id, new Map());
      map.get(config.employee_id)!.set(config.entity_type, config.visible_fields);
    }
    return map;
  }, [fieldVisibilityConfigs]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    // Üres keresésnél csak azokat mutatjuk, akiknek jelenleg van hozzáférése
    // (van jelszavuk) - gyors áttekintés, ki aktív. Amint gépelsz, az összes
    // munkatárs között keresünk, hogy újnak is meg tudd adni a hozzáférést.
    const matches = !q
      ? employees.filter((e) => e.has_password)
      : employees.filter((e) => e.full_name.toLowerCase().includes(q) || (e.email ?? "").toLowerCase().includes(q));
    return matches.slice(0, 20);
  }, [employees, query]);

  const selected = employees.find((e) => e.id === selectedId) ?? null;

  return (
    <div>
      {!selected && (
        <>
          <QuickCreateForm
            postPath="/api/v1/crew"
            addLabel="+ Teljesen új munkatárs hozzáadása"
            submitLabel="Létrehozás"
            presetFields={{ tipus: "belsos", role: "operator" }}
            fields={[
              { name: "full_name", label: "Név", required: true },
              { name: "email", label: "Email (felhasználónév)" },
              { name: "password", label: "Jelszó (min. 6 karakter)", type: "password", required: true },
            ]}
          />

          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Keresés név vagy email alapján…"
            className="mb-2 w-full max-w-sm rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none"
          />
          <div className="max-h-80 overflow-y-auto rounded-[var(--radius)] border border-border">
            {filtered.length === 0 && (
              <p className="p-3 text-[13px] text-text-muted">
                {query.trim() ? "Nincs találat." : "Jelenleg senkinek nincs hozzáférése - keress rá valakire, vagy adj hozzá egy új munkatársat."}
              </p>
            )}
            {filtered.map((e) => (
              <button
                key={e.id}
                type="button"
                onClick={() => setSelectedId(e.id)}
                className="flex w-full items-center justify-between border-b border-border px-3 py-2 text-left text-[13px] last:border-b-0 hover:bg-surface-3"
              >
                <span className="text-text-primary">{e.full_name}</span>
                <span className="text-text-muted">
                  {e.email ?? "nincs email"} · {ROLE_LABEL[e.role] ?? e.role}
                </span>
              </button>
            ))}
          </div>
          {!query.trim() && (
            <p className="mt-1.5 text-[12px] text-text-muted">
              Csak azok látszanak, akiknek jelenleg van hozzáférése - kereséssel bárkit megtalálsz.
            </p>
          )}
          {query.trim() && employees.length > filtered.length && (
            <p className="mt-1.5 text-[12px] text-text-muted">
              {filtered.length} találat megjelenítve - pontosítsd a keresést a további találatokhoz.
            </p>
          )}
        </>
      )}

      {selected && (
        <div className="space-y-4 rounded-[var(--radius)] border border-border p-3">
          <div className="flex items-center justify-between">
            <p className="text-[13px] font-medium text-text-primary">{selected.full_name}</p>
            <button
              type="button"
              onClick={() => setSelectedId(null)}
              className="text-[12px] text-text-accent hover:underline"
            >
              Másik munkatárs
            </button>
          </div>

          {/* Szerepkör: eddig csak KIÍRVA volt, átállítani nem lehetett -
              pedig pl. az Adminisztráció szerepkört valakihez hozzá kell tudni
              rendelni. */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[13px] text-text-secondary">Szerepkör:</span>
            <SelectDropdown
              value={ROLE_LABEL[selected.role] ?? selected.role}
              options={ROLE_ORDER.map((r) => ROLE_LABEL[r])}
              onChange={(label) => {
                const role = ROLE_ORDER.find((r) => ROLE_LABEL[r] === label);
                if (role) void mentSzerepkor(selected.id, role);
              }}
              placeholder="Szerepkör"
              disabled={szerepkorBusy}
            />
            {ROLE_LEIRAS[selected.role] && (
              <span className="text-[12px] text-text-muted">{ROLE_LEIRAS[selected.role]}</span>
            )}
          </div>

          <UserAccessManager
            employeeId={selected.id}
            employeeLabel={selected.full_name}
            initialEmail={selected.email}
            pages={pages}
            initialPagePermissions={pagePermissionsByEmployee.get(selected.id) ?? null}
            pageTabsMap={pageTabsMap}
            anyagok={anyagok}
            initialAnyagIdk={anyagKorlatByEmployee.get(selected.id) ?? null}
          />

          <div className="border-t border-border pt-4">
            <p className="mb-2 text-[13px] font-medium text-text-primary">Mező-láthatóság</p>
            <div className="space-y-2">
              {visibilityEntities.map((entity) => (
                <FieldVisibilityManager
                  key={entity.entityType}
                  patchPath={`/api/v1/field-visibility/${selected.id}/${entity.entityType}`}
                  entityLabel={entity.label}
                  availableFields={entity.availableFields}
                  initialVisible={fieldVisibilityByEmployee.get(selected.id)?.get(entity.entityType) ?? null}
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
