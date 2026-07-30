"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SelectDropdown } from "@/components/SelectDropdown";
import { authFetch } from "@/lib/authFetch";

const EMPLOYEE_PATH = "/api/v1/crew";
const RATE_PATH = "/api/v1/rates";

/** Munkatárs "aktív" jelzőjének helyben szerkesztése (checkbox, azonnal ment) -
 * a Vágók oldalon kell, hogy egyben látszódjon, ki dolgozik még nálunk. */
export function EmployeeActiveToggle({ employeeId, initialActive }: { employeeId: number; initialActive: boolean }) {
  const router = useRouter();
  const [checked, setChecked] = useState(initialActive);
  const [busy, setBusy] = useState(false);

  async function save(next: boolean) {
    setChecked(next);
    setBusy(true);
    try {
      const res = await authFetch(`${EMPLOYEE_PATH}/${employeeId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: next }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        setChecked(!next);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
      setChecked(!next);
    } finally {
      setBusy(false);
    }
  }

  return (
    <input
      type="checkbox"
      checked={checked}
      disabled={busy}
      onChange={(e) => save(e.target.checked)}
      className="h-4 w-4 accent-[var(--color-text-accent)]"
    />
  );
}

/** A tipus mező emberi nevei: az adatbázisban "kulsos"/"belsos" szerepel, a
 * felületen viszont ezt olvassa a felhasználó. */
const TIPUS_LABELS: Record<string, string> = { kulsos: "Külsős", belsos: "Belsős" };
const TIPUS_VALUES: Record<string, string> = { Külsős: "kulsos", Belsős: "belsos" };

/** Külsős/belsős jelölés helyben szerkesztése. A vágó-lista SZEREPKÖR (role)
 * alapján áll össze, a tipus pedig már csak ezt az egy kérdést dönti el -
 * ezért kell itt is látszania és állíthatónak lennie. */
export function EmployeeTipusSelect({ employeeId, initialValue }: { employeeId: number; initialValue: string | null }) {
  const router = useRouter();
  const [value, setValue] = useState(initialValue);
  const [busy, setBusy] = useState(false);

  async function save(label: string | null) {
    const next = label ? (TIPUS_VALUES[label] ?? null) : null;
    const elozo = value;
    setValue(next);
    setBusy(true);
    try {
      const res = await authFetch(`${EMPLOYEE_PATH}/${employeeId}`, {
        method: "PATCH",
        body: JSON.stringify({ tipus: next }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        setValue(elozo);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
      setValue(elozo);
    } finally {
      setBusy(false);
    }
  }

  return (
    <SelectDropdown
      value={value ? (TIPUS_LABELS[value] ?? value) : null}
      options={["Külsős", "Belsős"]}
      onChange={save}
      placeholder="Nincs megadva"
      disabled={busy}
    />
  );
}

/** Munkatárs "első munkanap" dátumának helyben szerkesztése - mikor kezdett
 * nálunk vágóként. */
export function EmployeeStartDateEditor({ employeeId, initialValue }: { employeeId: number; initialValue: string | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function save(value: string) {
    setBusy(true);
    try {
      const res = await authFetch(`${EMPLOYEE_PATH}/${employeeId}`, {
        method: "PATCH",
        body: JSON.stringify({ elso_munkanap: value || null }),
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
      setBusy(false);
    }
  }

  return (
    <input
      type="date"
      defaultValue={initialValue ?? ""}
      disabled={busy}
      onBlur={(e) => save(e.target.value)}
      className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
    />
  );
}

/** Óradíj (Rate.orabler) helyben szerkesztése - ha a munkatársnak még nincs
 * Rate sora, az első mentéskor létrehozunk egyet (POST), utána már csak
 * PATCH-eljük ugyanazt a sort. A RelatedTable/QuickCreateForm páros erre nem
 * alkalmas (nincs "szerkessz vagy hozz létre, ha még nincs" logikája), ezért
 * ez egy önálló, kis komponens. */
export function RateHourlyEditor({ employeeId, rateId, initialValue }: { employeeId: number; rateId: number | null; initialValue: number | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function save(raw: string) {
    const value = raw.trim() === "" ? null : Number(raw);
    if (raw.trim() !== "" && Number.isNaN(value)) {
      alert("Érvénytelen szám.");
      return;
    }
    setBusy(true);
    try {
      const res = rateId
        ? await authFetch(`${RATE_PATH}/${rateId}`, { method: "PATCH", body: JSON.stringify({ orabler: value }) })
        : await authFetch(RATE_PATH, { method: "POST", body: JSON.stringify({ employee_id: employeeId, orabler: value }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <input
      type="number"
      defaultValue={initialValue ?? ""}
      disabled={busy}
      placeholder="Ft/óra"
      onBlur={(e) => save(e.target.value)}
      className="w-24 rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
    />
  );
}
