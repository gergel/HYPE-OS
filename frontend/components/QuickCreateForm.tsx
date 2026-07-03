"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";

type FieldSpec = { name: string; label: string; type?: "text" | "date" | "number"; required?: boolean };

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
    setBusy(true);
    setError(null);
    try {
      const body: Record<string, unknown> = { ...presetFields };
      for (const f of fields) {
        if (values[f.name]) body[f.name] = f.type === "number" ? Number(values[f.name]) : values[f.name];
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
      className="mb-3 flex flex-wrap items-end gap-3 rounded-[var(--radius)] border border-border bg-surface-3 p-3"
    >
      {fields.map((f) => (
        <div key={f.name} className="flex flex-col gap-1">
          <label className="text-[11px] text-text-muted">
            {f.label}
            {f.required && " *"}
          </label>
          <input
            type={f.type ?? "text"}
            required={f.required}
            value={values[f.name] ?? ""}
            onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
            className="rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
          />
        </div>
      ))}
      <button
        type="submit"
        disabled={busy}
        className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-2 disabled:opacity-50"
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
