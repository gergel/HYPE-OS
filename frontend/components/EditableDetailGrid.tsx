"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/authFetch";
import { selectColor } from "@/lib/selectColor";
import type { EditableDetailField } from "@/lib/detail";

/** Egyetlen mező helyben szerkeszthető cellája - kattintásra input/textarea/
 * select jelenik meg (checkbox/select esetén azonnal ment), Enter/elkattintás
 * menti, Escape visszavonja. Csak azt a mezőt PATCH-eli, amit ténylegesen
 * módosítottak. */
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
    return <dd className="text-[13px] leading-relaxed text-text-primary break-words">{field.value ?? "Üres"}</dd>;
  }

  if (field.inputType === "boolean") {
    return (
      <dd>
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
    if (!editing) {
      return (
        <dd role="button" tabIndex={0} onClick={() => setEditing(true)} className="cursor-pointer">
          {current ? (
            <span
              className="inline-flex items-center gap-1.5 rounded-[var(--radius)] px-2 py-0.5 text-[13px]"
              style={{ background: selectColor(current).bg, color: selectColor(current).text }}
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: selectColor(current).text }} />
              {current}
            </span>
          ) : (
            <span className="rounded text-[13px] text-text-muted italic hover:bg-surface-3">Üres</span>
          )}
        </dd>
      );
    }
    return (
      <dd>
        <select
          autoFocus
          disabled={busy}
          value={current ?? ""}
          onChange={(e) => save(e.target.value || null)}
          onBlur={() => setEditing(false)}
          className="w-full max-w-xs rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none"
        >
          <option value="">Üres</option>
          {field.options?.map((opt) => (
            <option key={opt} value={opt} style={{ background: selectColor(opt).bg, color: selectColor(opt).text }}>
              {opt}
            </option>
          ))}
        </select>
      </dd>
    );
  }

  if (!editing) {
    return (
      <dd
        role="button"
        tabIndex={0}
        onClick={() => setEditing(true)}
        className="cursor-text rounded text-[13px] leading-relaxed text-text-primary break-words hover:bg-surface-3"
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
    className:
      "w-full rounded-[var(--radius)] border border-border bg-surface-2 px-2 py-1 text-[13px] text-text-primary focus:outline-none",
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

/** A DetailGrid szerkeszthető változata - Notion-stílusú, egymás alatt
 * elrendezett mezőlista (nem többoszlopos rács), hogy a kapcsolódó adatok
 * egyben, átláthatóan legyenek olvashatók (lásd referenciakép). Minden mező
 * kattintásra helyben szerkeszthetővé válik, és a megadott patchPath-ra
 * PATCH-eli a módosított mezőt. */
export function EditableDetailGrid({ patchPath, fields }: { patchPath: string; fields: EditableDetailField[] }) {
  return (
    <dl className="divide-y divide-border">
      {fields.map((f) => (
        <div key={f.key} className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-start sm:gap-4">
          <dt className="shrink-0 text-[13px] text-text-muted sm:w-52">{f.label}</dt>
          <div className="min-w-0 flex-1">
            <EditableCell patchPath={patchPath} field={f} />
          </div>
        </div>
      ))}
    </dl>
  );
}
