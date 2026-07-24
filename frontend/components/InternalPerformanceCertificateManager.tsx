"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { PendingBelsosTigEmployee } from "@/lib/api";

type FormState = {
  netto_osszeg: string;
  plusz_afa: boolean;
  teljesites_kezdete: string;
  teljesites_vege: string;
  megjegyzes: string;
};

function formFromEmployee(employee: PendingBelsosTigEmployee): FormState {
  const draft = employee.draft;
  return {
    netto_osszeg: draft?.netto_osszeg != null ? String(draft.netto_osszeg) : "",
    plusz_afa: draft?.plusz_afa ?? false,
    teljesites_kezdete: draft?.teljesites_kezdete ?? "",
    teljesites_vege: draft?.teljesites_vege ?? "",
    megjegyzes: draft?.megjegyzes ?? "",
  };
}

function computeBrutto(nettoOsszeg: string, pluszAfa: boolean): number | null {
  if (!nettoOsszeg.trim()) return null;
  const netto = Number(nettoOsszeg);
  if (Number.isNaN(netto)) return null;
  return pluszAfa ? Math.round(netto * 1.27 * 100) / 100 : netto;
}

/** Belsős TIG - a PerformanceCertificateManager (Külsős TIG) párja, de
 * egyszerűbb: nincs cégadat/Google Docs sablon, csak egy összeg rögzítése,
 * ami "Kész" jelölés után jöhet a TigInvoiceManager-es számla-feltöltés
 * (lásd projektek/[id]/page.tsx, ahol mindkét manager egymás mellett
 * szerepel). */
export function InternalPerformanceCertificateManager({
  projectId,
  pending,
}: {
  projectId: number;
  pending: PendingBelsosTigEmployee[];
}) {
  const router = useRouter();
  const [selectedId, setSelectedId] = useState<number | "">("");
  const [openId, setOpenId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [busy, setBusy] = useState<"save" | "kesz" | "skip" | null>(null);

  const selectedEmployee = pending.find((p) => p.id === openId) ?? null;
  const bruttoOsszeg = form ? computeBrutto(form.netto_osszeg, form.plusz_afa) : null;

  function openForm() {
    if (!selectedId) return;
    const employee = pending.find((p) => p.id === selectedId);
    if (!employee) return;
    setForm(formFromEmployee(employee));
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
      teljesites_kezdete: form.teljesites_kezdete || null,
      teljesites_vege: form.teljesites_vege || null,
      megjegyzes: form.megjegyzes || null,
    };
  }

  async function handleSave() {
    if (!selectedEmployee || !form) return;
    setBusy("save");
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${projectId}/${selectedEmployee.id}/save`, {
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
      setBusy(null);
    }
  }

  async function handleKesz() {
    if (!selectedEmployee || !form) return;
    if (!form.netto_osszeg.trim() || Number.isNaN(Number(form.netto_osszeg)) || Number(form.netto_osszeg) <= 0) {
      alert("Add meg a nettó összeget.");
      return;
    }
    setBusy("kesz");
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${projectId}/${selectedEmployee.id}/kesz`, {
        method: "POST",
        body: JSON.stringify(buildPayload()),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      closeForm();
      setSelectedId("");
      router.refresh();
    } catch (err) {
      alert(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  async function handleSkip() {
    if (!selectedEmployee) return;
    if (!confirm(`Biztosan kihagyod ${selectedEmployee.full_name}-t?`)) return;
    setBusy("skip");
    try {
      const res = await authFetch(`/api/v1/belsos-tig/${projectId}/${selectedEmployee.id}/skip`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen kihagyás: ${detail?.detail ?? res.status}`);
        return;
      }
      closeForm();
      setSelectedId("");
      router.refresh();
    } catch (err) {
      alert(`Sikertelen kihagyás (hálózati hiba): ${err}`);
    } finally {
      setBusy(null);
    }
  }

  const busyState = busy !== null;

  return (
    <div>
      <p className="mb-3 text-[13px] text-text-secondary">
        {pending.length === 0
          ? "Nincs olyan belsős munkatárs a projekten, akinek Belsős TIG-et kellene készíteni."
          : `${pending.length} belsős munkatársnak kell Belsős TIG.`}
      </p>
      {pending.length > 0 && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] text-text-muted">Munkatárs</label>
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value ? Number(e.target.value) : "")}
              className="min-w-[220px] rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none"
            >
              <option value="">Válassz munkatársat…</option>
              {pending.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.full_name}
                  {p.draft ? ` (${p.draft.allapot ?? "Készítés alatt"})` : ""}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={openForm}
            disabled={!selectedId}
            className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
          >
            Belsős TIG készítése
          </button>
        </div>
      )}

      {selectedEmployee && form && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={busyState ? undefined : closeForm}>
          <div
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-[var(--radius)] border border-border bg-surface-2 p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="mb-1 text-[15px] font-medium text-text-primary">Belsős TIG – {selectedEmployee.full_name}</h3>
            <p className="mb-4 text-[12px] text-text-muted">Állapot: {selectedEmployee.draft?.allapot ?? "Nincs elkezdve"}</p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label="Nettó összeg (Ft) *">
                <input
                  type="number"
                  value={form.netto_osszeg}
                  onChange={(e) => update("netto_osszeg", e.target.value)}
                  disabled={busyState}
                  className={inputClass}
                />
              </Field>
              <Field label="PLUSZ áfa">
                <label className="flex items-center gap-2 py-1.5 text-[13px] text-text-primary">
                  <input
                    type="checkbox"
                    checked={form.plusz_afa}
                    onChange={(e) => update("plusz_afa", e.target.checked)}
                    disabled={busyState}
                  />
                  {form.plusz_afa ? "Igen" : "Nem"}
                </label>
              </Field>
              <Field label="Bruttó összeg (Ft)">
                <p className="py-1.5 text-[13px] text-text-secondary">
                  {bruttoOsszeg != null ? `${bruttoOsszeg.toLocaleString("hu-HU")} Ft` : "–"}
                </p>
              </Field>
              <Field label="Teljesítés kezdete">
                <input
                  type="date"
                  value={form.teljesites_kezdete}
                  onChange={(e) => update("teljesites_kezdete", e.target.value)}
                  disabled={busyState}
                  className={inputClass}
                />
              </Field>
              <Field label="Teljesítés vége">
                <input
                  type="date"
                  value={form.teljesites_vege}
                  onChange={(e) => update("teljesites_vege", e.target.value)}
                  disabled={busyState}
                  className={inputClass}
                />
              </Field>
              <Field label="Megjegyzés">
                <input
                  value={form.megjegyzes}
                  onChange={(e) => update("megjegyzes", e.target.value)}
                  disabled={busyState}
                  className={inputClass}
                />
              </Field>
            </div>
            <div className="mt-5 flex flex-wrap justify-end gap-3 border-t border-border pt-4">
              <button
                type="button"
                onClick={closeForm}
                disabled={busyState}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                Bezárás
              </button>
              <button
                type="button"
                onClick={handleSkip}
                disabled={busyState}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busy === "skip" ? "Kihagyás…" : "Kihagyás"}
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={busyState}
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3 disabled:opacity-50"
              >
                {busy === "save" ? "Mentés…" : "Mentés"}
              </button>
              <button
                type="button"
                onClick={handleKesz}
                disabled={busyState}
                className="rounded-[var(--radius)] border border-border bg-bg-accent px-3 py-1.5 text-[13px] text-text-accent hover:opacity-90 disabled:opacity-50"
              >
                {busy === "kesz" ? "Mentés…" : "Kész (jöhet a számla)"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const inputClass =
  "w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-primary focus:outline-none";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] text-text-muted">{label}</label>
      {children}
    </div>
  );
}
