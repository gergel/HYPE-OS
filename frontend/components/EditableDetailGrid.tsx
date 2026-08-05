"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SelectDropdown } from "@/components/SelectDropdown";
import { authFetch } from "@/lib/authFetch";
import type { EditableDetailField } from "@/lib/detail";

/** Egyetlen mező helyben szerkeszthető cellája - kattintásra input/textarea/
 * select jelenik meg (checkbox/select esetén azonnal ment), Enter/elkattintás
 * menti, Escape visszavonja. Csak azt a mezőt PATCH-eli, amit ténylegesen
 * módosítottak.
 *
 * boxed: ha igaz, a mező NYUGALMI állapotban is látható szegéllyel/dobozzal
 * jelenik meg (form-mező kinézet, lásd referenciakép: minden mező úgy néz
 * ki, mint egy input, nem csak kattintáskor) - a szerkesztés-logika
 * (kattintás -> input, Enter/elkattintás -> mentés) változatlan, csak a
 * nyugalmi állapot vizuálja tér el a Notion-stílusú "sima szöveg" nézettől. */
function EditableCell({ patchPath, field, boxed = false }: { patchPath: string; field: EditableDetailField; boxed?: boolean }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  // Az <input type="time"> csak "HH:MM"-et fogad el (a backend "08:00:00"-t
  // ad vissza a Time oszlopból), ezért a másodperceket levágjuk - enélkül a
  // böngésző üresnek mutatná a mezőt, mintha nem lenne beállítva időpont.
  const initialDraft =
    field.rawValue === null
      ? ""
      : field.inputType === "time"
        ? String(field.rawValue).slice(0, 5)
        : String(field.rawValue);
  const [draft, setDraft] = useState<string>(initialDraft);
  const [busy, setBusy] = useState(false);

  const restBoxClass = boxed
    ? "rounded-[var(--radius)] border border-border bg-surface-3 px-3 py-2 min-h-[38px] transition-colors duration-200 hover:border-border-strong"
    : "";

  async function save(value: unknown) {
    setBusy(true);
    try {
      const res = await authFetch(patchPath, { method: "PATCH", body: JSON.stringify({ [field.key]: value }) });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        alert(`Sikertelen mentés: ${detail?.detail ?? res.status}`);
        return;
      }
      setEditing(false);
      router.refresh();
    } catch (err) {
      alert(`Sikertelen mentés (hálózati hiba): ${err}`);
    } finally {
      setBusy(false);
    }
  }

  if (!field.editable) {
    return (
      <dd className={`text-[13px] leading-relaxed text-text-primary break-words ${restBoxClass}`}>{field.value ?? "Üres"}</dd>
    );
  }

  if (field.inputType === "boolean") {
    return (
      <dd className={boxed ? `flex items-center ${restBoxClass}` : undefined}>
        <input
          type="checkbox"
          checked={Boolean(field.rawValue)}
          disabled={busy}
          onChange={(e) => save(e.target.checked)}
          className="h-4 w-4 accent-[var(--color-text-accent)]"
        />
      </dd>
    );
  }

  if (field.inputType === "select") {
    const current = field.rawValue === null || field.rawValue === "" ? null : String(field.rawValue);
    return (
      <dd>
        <SelectDropdown
          value={current}
          options={field.options ?? []}
          onChange={(next) => save(next)}
          disabled={busy}
          placeholder="Üres"
          className={boxed ? "w-full" : undefined}
          allowNew={field.allowNew}
        />
      </dd>
    );
  }

  if (!editing) {
    return (
      <dd
        role="button"
        tabIndex={0}
        onClick={() => setEditing(true)}
        className={`cursor-text text-[13px] leading-relaxed text-text-primary break-words ${boxed ? restBoxClass : "-mx-1.5 rounded px-1.5 transition-colors duration-200 hover:bg-surface-3"}`}
      >
        {field.value ?? <span className="text-text-muted italic">Üres</span>}
      </dd>
    );
  }

  const commonProps = {
    autoFocus: true,
    disabled: busy,
    value: draft,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setDraft(e.target.value),
    onBlur: () => save(field.inputType === "number" ? Number(draft) || null : draft || null),
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === "Escape") setEditing(false);
      if (e.key === "Enter" && field.inputType !== "textarea") {
        save(field.inputType === "number" ? Number(draft) || null : draft || null);
      }
    },
    className: "field w-full",
  };

  return (
    <dd>
      {field.inputType === "textarea" ? (
        <textarea rows={4} {...commonProps} />
      ) : (
        <input
          type={
            field.inputType === "date"
              ? "date"
              : field.inputType === "time"
                ? "time"
                : field.inputType === "number"
                  ? "number"
                  : "text"
          }
          {...commonProps}
        />
      )}
    </dd>
  );
}

/** A DetailGrid szerkeszthető változata - Notion-stílusú, egymás alatt
 * elrendezett mezőlista (nem többoszlopos rács), hogy a kapcsolódó adatok
 * egyben, átláthatóan legyenek olvashatók (lásd referenciakép). Minden mező
 * kattintásra helyben szerkeszthetővé válik, és a megadott patchPath-ra
 * PATCH-eli a módosított mezőt. */
export function EditableDetailGrid({
  patchPath,
  fields,
  readOnly = false,
  layout = "row",
}: {
  patchPath: string;
  fields: EditableDetailField[];
  /** Ha igaz, minden mező csak olvashatóként jelenik meg (nincs PATCH-küldés) -
   * a fül-szintű szerkesztési jogosultság hiányában (lásd lib/detailTabs.tsx),
   * hogy a felhasználó lássa az adatot, de ne módosíthassa. */
  readOnly?: boolean;
  /** "row" (alapértelmezett): Notion-stílusú, címke balra/érték jobbra sor.
   * "boxed": címke fent, alatta mindig látható szegélyű doboz (form-mező
   * kinézet, lásd referenciakép) - a részletnézet szekció-kártyáiban
   * használt elrendezés (lásd lib/detailTabs.tsx). */
  layout?: "row" | "boxed";
}) {
  const effectiveFields = readOnly ? fields.map((f) => ({ ...f, editable: false })) : fields;

  if (layout === "boxed") {
    return (
      <dl className="grid grid-cols-1 gap-x-5 gap-y-4 sm:grid-cols-2">
        {effectiveFields.map((f) => (
          <div key={f.key} className={`flex flex-col gap-1.5 ${f.wide ? "sm:col-span-2" : ""}`}>
            <dt className="t-label">{f.label}</dt>
            <EditableCell patchPath={patchPath} field={f} boxed />
          </div>
        ))}
      </dl>
    );
  }

  return (
    <dl className="divide-y divide-border">
      {effectiveFields.map((f) => (
        <div key={f.key} className="flex flex-col gap-1.5 py-3 sm:flex-row sm:items-start sm:gap-6">
          <dt className="shrink-0 text-[13px] text-text-muted sm:w-52">{f.label}</dt>
          <div className="min-w-0 flex-1">
            <EditableCell patchPath={patchPath} field={f} />
          </div>
        </div>
      ))}
    </dl>
  );
}
