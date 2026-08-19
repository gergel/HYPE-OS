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
  /** Előre beírt kezdőérték (pl. a projektkód "HYPE26-" előtagja) - a mező
   * ettől még szabadon átírható. Az űrlap minden megnyitásakor visszaáll rá. */
  defaultValue?: string;
  placeholder?: string;
  /** Csak akkor jelenjen meg, ha egy MÁSIK mező értéke ilyen - pl. az
   * árfolyamot csak devizás pénznemnél kérdezzük. Egy mindig ott álló,
   * legtöbbször üresen hagyott mező zajt visz az űrlapra, és azt sugallja,
   * hogy kellene kitölteni.
   *
   * SZÁNDÉKOSAN adat, nem függvény: az űrlapot szerver-komponensek állítják
   * össze (lásd penzugyek/page.tsx), egy függvényt pedig nem lehet átadni
   * kliens-komponensnek ("Functions cannot be passed directly to Client
   * Components"). */
  showIf?: { field: string; oneOf?: string[]; noneOf?: string[] };
};

/** Látszik-e ez a mező a mostani beírások mellett (lásd FieldSpec.showIf)? */
function lathato(f: FieldSpec, values: Record<string, string>): boolean {
  if (!f.showIf) return true;
  const ertek = values[f.showIf.field] ?? "";
  if (f.showIf.oneOf && !f.showIf.oneOf.includes(ertek)) return false;
  if (f.showIf.noneOf && f.showIf.noneOf.includes(ertek)) return false;
  return true;
}

/** A mezők kezdőértékei - az űrlap minden megnyitásakor ezzel indul. */
function kezdoErtekek(fields: FieldSpec[]): Record<string, string> {
  return Object.fromEntries(
    fields.filter((f) => f.defaultValue !== undefined).map((f) => [f.name, f.defaultValue as string]),
  );
}

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
  const [values, setValues] = useState<Record<string, string>>(() => kezdoErtekek(fields));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // A rejtett mezők nem is léteznek: se validálni, se elküldeni nem kell őket.
  const lathatoMezok = fields.filter((f) => lathato(f, values));

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    // Ne csak a böngésző natív "required" tooltipjére hagyatkozzunk - az
    // könnyen észrevétlen marad (pl. ha a mező máshova görgetve van), és
    // ilyenkor a kattintás úgy nézett ki, mintha semmi nem történt volna
    // (nem ment ki kérés a szerver felé). Explicit, jól látható hibaüzenetet
    // adunk ilyenkor is.
    const missing = lathatoMezok.filter((f) => f.required && !values[f.name]?.trim());
    if (missing.length > 0) {
      setError(`Kötelező mező hiányzik: ${missing.map((f) => f.label).join(", ")}`);
      return;
    }
    setBusy(true);
    try {
      const body: Record<string, unknown> = { ...presetFields };
      for (const f of lathatoMezok) {
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
      setValues(kezdoErtekek(fields));
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
      <button
        type="button"
        // Nyitáskor is visszaállunk a kezdőértékekre: egy félbehagyott,
        // "Mégse"-vel bezárt űrlap után ne a régi gépelés fogadjon.
        onClick={() => {
          setValues(kezdoErtekek(fields));
          setError(null);
          setOpen(true);
        }}
        className="mb-2 text-[13px] text-text-accent hover:underline"
      >
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
      {lathatoMezok.map((f) => (
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
              placeholder={f.placeholder}
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
