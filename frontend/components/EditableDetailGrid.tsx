"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import type { EditableDetailField } from "@/lib/detail";

/** Egyetlen mező helyben szerkeszthető cellája - kattintásra input/textarea
 * jelenik meg (checkbox esetén azonnal ment), Enter/elkattintás menti, Escape
 * visszavonja. Csak azt a mezőt PATCH-eli, amit ténylegesen módosítottak. */
function EditableCell({ patchPath, field }: { patchPath: string; field: EditableDetailField }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<string>(field.rawValue === null ? "" : String(field.rawValue));
  const [busy, setBusy] = useState(false);

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
    return <dd className="mt-0.5 text-[13px] leading-relaxed text-text-primary break-words">{field.value ?? "–"}</dd>;
  }

  if (field.inputType === "boolean") {
    return (
      <dd className="mt-0.5">
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

  if (!editing) {
    return (
      <dd
        role="button"
        tabIndex={0}
        onClick={() => setEditing(true)}
        className="mt-0.5 cursor-text rounded text-[13px] leading-relaxed text-text-primary break-words hover:bg-surface-3"
      >
        {field.value ?? "–"}
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
    className:
      "mt-0.5 w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none",
  };

  return (
    <dd>
      {field.inputType === "textarea" ? (
        <textarea rows={4} {...commonProps} />
      ) : (
        <input type={field.inputType === "date" ? "date" : field.inputType === "number" ? "number" : "text"} {...commonProps} />
      )}
    </dd>
  );
}

/** A DetailGrid szerkeszthető változata - minden mező kattintásra helyben
 * szerkeszthetővé válik (mint egy Notion-adatbázis), és a megadott patchPath-ra
 * PATCH-eli a módosított mezőt. */
export function EditableDetailGrid({ patchPath, fields }: { patchPath: string; fields: EditableDetailField[] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">
      {fields.map((f) => (
        <div key={f.key} className={f.wide ? "sm:col-span-2 lg:col-span-3" : undefined}>
          <dt className="text-[12px] text-text-muted">{f.label}</dt>
          <EditableCell patchPath={patchPath} field={f} />
        </div>
      ))}
    </dl>
  );
}
