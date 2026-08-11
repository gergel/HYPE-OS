"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { KeresosSelect } from "@/components/KeresosSelect";

type FieldSpec = {
  name: string;
  label: string;
  type?: "text" | "date" | "number" | "password" | "select";
  required?: boolean;
  /** "select" típusnál a legördülő opciói - pl. egy foreign key mezőhöz
   * (ügyfél/project code kiválasztása név szerint, ID begépelés helyett). */
  options?: { value: number | string; label: string }[];
};

/** Kis inline form egy új, kapcsolódó rekord létrehozásához (pl. egy projekthez új
 * utómunka), a szükséges foreign key-ket előre kitöltve (`presetFields`) küldi -
 * a felhasználó csak a néhány releváns mezőt látja, nem a teljes ~140 mezős sémát. */
export function QuickCreateForm({
  postPath,
  fields,
  presetFields = {},
  addLabel = "+ Új hozzáadása",
  submitLabel = "Hozzáadás",
}: {
  postPath: string;
  fields: FieldSpec[];
  presetFields?: Record<string, unknown>;
  addLabel?: string;
  submitLabel?: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    // Ne csak a böngésző natív "required" tooltipjére hagyatkozzunk - az
    // könnyen észrevétlen marad (pl. ha a mező máshova görgetve van), és
    // ilyenkor a kattintás úgy nézett ki, mintha semmi nem történt volna
    // (nem ment ki kérés a szerver felé). Explicit, jól látható hibaüzenetet
    // adunk ilyenkor is.
    const missing = fields.filter((f) => f.required && !values[f.name]?.trim());
    if (missing.length > 0) {
      setError(`Kötelező mező hiányzik: ${missing.map((f) => f.label).join(", ")}`);
      return;
    }
    setBusy(true);
    try {
      const body: Record<string, unknown> = { ...presetFields };
      for (const f of fields) {
        if (!values[f.name]) continue;
        const isNumericSelect = f.type === "select" && typeof f.options?.[0]?.value === "number";
        body[f.name] = f.type === "number" || isNumericSelect ? Number(values[f.name]) : values[f.name];
      }
      const res = await authFetch(postPath, { method: "POST", body: JSON.stringify(body) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        setError(`Sikertelen: ${detail?.detail ?? res.status}`);
        return;
      }
      setValues({});
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(`Sikertelen (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="mb-2 text-[13px] text-text-accent hover:underline">
        {addLabel}
      </button>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="fade-in mb-4 flex flex-wrap items-end gap-4 rounded-[var(--radius-lg)] border border-border bg-surface-3 p-4"
    >
      {fields.map((f) => (
        <div key={f.name} className="flex flex-col gap-1">
          <label className="t-label">
            {f.label}
            {f.required && " *"}
          </label>
          {f.type === "select" ? (
            <KeresosSelect
              value={values[f.name] || null}
              options={(f.options ?? []).map((opt) => ({ value: String(opt.value), label: opt.label }))}
              onChange={(ertek) => setValues((v) => ({ ...v, [f.name]: ertek }))}
              placeholder="Válassz…"
              className="min-w-[200px]"
            />
          ) : (
            <input
              type={f.type ?? "text"}
              required={f.required}
              value={values[f.name] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
              className="field"
            />
          )}
        </div>
      ))}
      <button
        type="submit"
        disabled={busy}
        className="btn btn-primary"
      >
        {busy ? "Mentés…" : submitLabel}
      </button>
      <button type="button" onClick={() => setOpen(false)} className="text-[13px] text-text-muted hover:text-text-primary">
        Mégse
      </button>
      {error && <p className="w-full text-[12px] text-text-danger">{error}</p>}
    </form>
  );
}
