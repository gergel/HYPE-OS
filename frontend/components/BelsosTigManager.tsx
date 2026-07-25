"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { useConfirm } from "@/components/ConfirmProvider";
import { StatusBadge } from "@/components/StatusBadge";
import type { BelsosTigMonthEmployee } from "@/lib/api";

type FormState = {
  netto_osszeg: string;
  plusz_afa: boolean;
  megjegyzes: string;
};

function formFromRecord(employee: BelsosTigMonthEmployee): FormState {
  const record = employee.record;
  return {
    netto_osszeg: record?.netto_osszeg != null ? String(record.netto_osszeg) : "",
    plusz_afa: record?.plusz_afa ?? false,
    megjegyzes: record?.megjegyzes ?? "",
  };
}

function computeBrutto(nettoOsszeg: string, pluszAfa: boolean): number | null {
  if (!nettoOsszeg.trim()) return null;
  const netto = Number(nettoOsszeg);
  if (Number.isNaN(netto)) return null;
  return pluszAfa ? Math.round(netto * 1.27 * 100) / 100 : netto;
}

function statusBadge(employee: BelsosTigMonthEmployee) {
  const allapot = employee.record?.allapot;
  if (allapot === "Kész") return <StatusBadge label="Kész" tone="success" />;
  if (allapot === "Kihagyva") return <StatusBadge label="Kihagyva" tone="neutral" />;
  if (allapot === "Készítés alatt") return <StatusBadge label="Készítés alatt" tone="warning" />;
  return <StatusBadge label="Nincs elkezdve" tone="neutral" />;
}

const inputClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

/** Belsős TIG - havi admin oldal (lásd app/(app)/belsos-tig/page.tsx), ami az
 * adott hónap (alapértelmezetten a folyó hónap) összes belsős munkatársát
 * felsorolja, egy sorban mindegyiket. Ellentétben a Külsős TIG-gel, ez NEM
 * projektenkénti - egy embernek egy hónapban pontosan egy TIG-je van, amit
 * itt admin rögzít (összeg, majd "Kész"), vagy kihagy ("Kihagyva", ha az
 * illető épp nem dolgozott azon a hónapon). "Kész" után jöhet a számla
 * feltöltése és kifizetettként jelölése, ami létrehozza a Pénzügy ->
 * Kiadások-ban megjelenő Expense sort (lásd backend
 * internal_performance_certificates.py /szamla és /szamla-kifizetve). */
export function BelsosTigManager({ ev, honap, employees }: { ev: number; honap: number; employees: BelsosTigMonthEmployee[] }) {
  const router = useRouter();
  const confirm = useConfirm();
  const [openId, setOpenId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const openEmployee = employees.find((e) => e.id === openId) ?? null;
  const bruttoOsszeg = form ? computeBrutto(form.netto_osszeg, form.plusz_afa) : null;

  function openForm(employee: BelsosTigMonthEmployee) {
    setForm(formFromRecord(employee));
    setOpenId(employee.id);
  }

  function closeForm() {
    setOpenId(null);
    setForm(null);
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function buildPayload() {
    if (!form) return null;
    return {
      netto_osszeg: form.netto_osszeg.trim() ? Number(form.netto_osszeg) : null,
      plusz_afa: form.plusz_afa,
      megjegyzes: form.megjegyzes || null,
    };
  }

  async function handleSave() {
    if (!openEmployee) return;
    setBusyId(openEmployee.id);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${openEmployee.id}/${ev}/${honap}/save`, {
        method: "POST",
        body: JSON.stringify(buildPayload()),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      closeForm();
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  async function handleKesz() {
    if (!openEmployee || !form) return;
    if (!form.netto_osszeg.trim() || Number.isNaN(Number(form.netto_osszeg)) || Number(form.netto_osszeg) <= 0) {
      alert("Add meg a nettó összeget.");
      return;
    }
    setBusyId(openEmployee.id);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${openEmployee.id}/${ev}/${honap}/kesz`, {
        method: "POST",
        body: JSON.stringify(buildPayload()),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      closeForm();
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  async function handleSkip(employee: BelsosTigMonthEmployee) {
    if (!(await confirm(`Biztosan kihagyod ${employee.full_name}-t ebben a hónapban?`))) return;
    setBusyId(employee.id);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${employee.id}/${ev}/${honap}/skip`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen kihagyás: ${detail?.detail ?? res.status}`);
        return;
      }
      closeForm();
      router.refresh();
    } catch (err) {
      alert(`Sikertelen kihagyás (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  /** Egyszerre több kiválasztott fájl is feltölthető - egymás után megy fel,
   * mert minden hívás egy külön számla-sort hoz létre a backenden. */
  async function uploadSzamla(employee: BelsosTigMonthEmployee, input: HTMLInputElement, files: File[]) {
    setBusyId(employee.id);
    try {
      for (const file of files) {
        const fd = new FormData();
        fd.append("file", file);
        const res = await authFetch(`/api/v1/belsos-tig/${employee.id}/${ev}/${honap}/szamla`, { method: "POST", body: fd });
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          alert(`Sikertelen feltöltés (${file.name}): ${detail?.detail ?? res.status}`);
          break;
        }
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen feltöltés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
      input.value = "";
    }
  }

  async function deleteSzamla(employee: BelsosTigMonthEmployee, invoiceId: number, filename: string) {
    if (!(await confirm(`Biztosan törlöd ezt a számlát: "${filename}"?`))) return;
    setBusyId(employee.id);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${employee.id}/${ev}/${honap}/szamla/${invoiceId}`, { method: "DELETE" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen törlés: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen törlés (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  async function markKifizetve(employee: BelsosTigMonthEmployee) {
    if (!(await confirm("Kifizetettként jelölöd a számlát? Ez létrehoz (vagy frissít) egy Kiadás sort a Pénzügyben."))) return;
    setBusyId(employee.id);
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${employee.id}/${ev}/${honap}/szamla-kifizetve`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-border">
            <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Munkatárs</th>
            <th className="py-1.5 pr-6 text-left font-medium text-text-secondary">Állapot</th>
            <th className="py-1.5 pr-6 text-right font-medium text-text-secondary">Bruttó</th>
            <th className="min-w-[240px] py-1.5 pr-6 text-left font-medium text-text-secondary">Számlák</th>
            <th className="py-1.5 text-right font-medium text-text-secondary">Kifizetés</th>
          </tr>
        </thead>
        <tbody>
          {employees.map((employee) => {
            const record = employee.record;
            const allapot = record?.allapot;
            const isTerminal = allapot === "Kész" || allapot === "Kihagyva";
            const isKesz = allapot === "Kész";
            const busy = busyId === employee.id;
            const invoices = record?.invoices ?? [];
            return (
              <tr key={employee.id} className="border-b border-border last:border-0 align-top">
                <td className="py-3 pr-6">{employee.full_name}</td>
                <td className="py-3 pr-6">{statusBadge(employee)}</td>
                <td className="py-3 pr-6 text-right whitespace-nowrap">
                  {record?.brutto_osszeg != null ? `${record.brutto_osszeg.toLocaleString("hu-HU")} Ft` : "–"}
                </td>
                <td className="py-3 pr-6">
                  {!isKesz ? (
                    <span className="text-text-muted">–</span>
                  ) : (
                    <div className="flex flex-col gap-1.5">
                      {invoices.map((inv) => (
                        <div key={inv.id} className="flex items-center gap-2">
                          <a
                            href={inv.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="max-w-[180px] truncate text-text-accent hover:underline"
                            title={inv.filename}
                          >
                            {inv.filename}
                          </a>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => deleteSzamla(employee, inv.id, inv.filename)}
                            className="rounded-[var(--radius)] p-1 text-text-muted hover:bg-surface-3 hover:text-text-danger disabled:opacity-50"
                            title="Számla törlése"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      ))}
                      <label className="w-fit cursor-pointer text-[12px] text-text-accent hover:underline">
                        {busy ? "Feltöltés…" : "+ Számla feltöltése"}
                        <input
                          type="file"
                          multiple
                          disabled={busy}
                          onChange={(e) => {
                            const files = Array.from(e.target.files ?? []);
                            if (files.length > 0) uploadSzamla(employee, e.target, files);
                          }}
                          className="hidden"
                        />
                      </label>
                    </div>
                  )}
                </td>
                <td className="py-3 text-right">
                  {!isTerminal ? (
                    <button
                      type="button"
                      onClick={() => openForm(employee)}
                      disabled={busy}
                      className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                    >
                      TIG készítése
                    </button>
                  ) : isKesz && record?.szamla_kifizetve ? (
                    <StatusBadge label="Kifizetve" tone="success" />
                  ) : isKesz && invoices.length > 0 ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => markKifizetve(employee)}
                      className="rounded-[var(--radius)] border border-border px-2 py-1 text-[12px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
                    >
                      Kifizetve jelölés
                    </button>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {openEmployee && form && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={busyId ? undefined : closeForm}>
          <div
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">
              Belsős TIG – {openEmployee.full_name} ({ev}.{String(honap).padStart(2, "0")})
            </h3>
            <p className="mb-4 text-[12px] text-text-muted">Állapot: {openEmployee.record?.allapot ?? "Nincs elkezdve"}</p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Nettó összeg (Ft) *</label>
                <input
                  type="number"
                  value={form.netto_osszeg}
                  onChange={(e) => update("netto_osszeg", e.target.value)}
                  disabled={!!busyId}
                  className={inputClass}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">PLUSZ áfa</label>
                <label className="flex items-center gap-2 py-1.5 text-[13px] text-text-primary">
                  <input
                    type="checkbox"
                    checked={form.plusz_afa}
                    onChange={(e) => update("plusz_afa", e.target.checked)}
                    disabled={!!busyId}
                  />
                  {form.plusz_afa ? "Igen" : "Nem"}
                </label>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Bruttó összeg (Ft)</label>
                <p className="py-1.5 text-[13px] text-text-secondary">
                  {bruttoOsszeg != null ? `${bruttoOsszeg.toLocaleString("hu-HU")} Ft` : "–"}
                </p>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[11px] text-text-muted">Megjegyzés</label>
                <input
                  value={form.megjegyzes}
                  onChange={(e) => update("megjegyzes", e.target.value)}
                  disabled={!!busyId}
                  className={inputClass}
                />
              </div>
            </div>
            <div className="mt-5 flex flex-wrap justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={closeForm}
                disabled={!!busyId}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Bezárás
              </button>
              <button
                type="button"
                onClick={() => handleSkip(openEmployee)}
                disabled={!!busyId}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busyId === openEmployee.id ? "Kihagyás…" : "Kihagyás"}
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={!!busyId}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busyId === openEmployee.id ? "Mentés…" : "Mentés"}
              </button>
              <button
                type="button"
                onClick={handleKesz}
                disabled={!!busyId}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {busyId === openEmployee.id ? "Mentés…" : "Kész (jöhet a számla)"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
