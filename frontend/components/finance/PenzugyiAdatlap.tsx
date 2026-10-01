import type { ReactNode } from "react";
import { Card } from "@/components/Card";
import type { DetailSection } from "@/components/DetailSections";
import { DetailSections } from "@/components/DetailSections";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { StatusBadge } from "@/components/StatusBadge";
import type { FieldTypeInfo } from "@/lib/api";
import { toEditableDetailFields, type EditableDetailField } from "@/lib/detail";

/** A pénzügyi tételek (kiadás, bevétel) RENDEZETT adatlapja (a felhasználó
 * kérése, 2026-10): a korábbi, minden mezőt egy listába öntő nézet helyett
 * csak a fontos mezők, szekció-kártyákba csoportosítva - ugyanazzal a
 * kártyás, dobozos elrendezéssel, mint a diszpó (projekt) adatlapja. A
 * Notionből átjött, már nem használt mezők egy alapból CSUKOTT „Régi adatok”
 * blokkba kerülnek (csak a nem üresek), hogy semmi ne vesszen el szem elől. */

export type MezoDef = string | { key: string; label: string };

export type SzekcioDef = {
  key: string;
  cim: string;
  mezok: MezoDef[];
  /** A mezők alá kerülő egyéb tartalom (pl. számlafeltöltés). */
  extra?: ReactNode;
  /** Hamis: a szekció ki sem rajzolódik (pl. külsős adatok belsős tételnél). */
  lathato?: boolean;
};

/** Ezek sosem jelennek meg külön mezőként (azonosítók, technikai mezők). */
const SOSE: ReadonlySet<string> = new Set(["id", "created_at", "updated_at"]);

function ures(f: EditableDetailField): boolean {
  if (f.rawValue === null || f.rawValue === undefined || f.rawValue === "") {
    // Az objektum/tömb mezők rawValue-ja null - a megjelenített érték dönt.
    return f.value === null || f.value === undefined || f.value === "" || f.value === "–";
  }
  return false;
}

export function PenzugyiSzekciok({
  record,
  fieldTypes,
  visibleFields,
  patchPath,
  szekciok,
  readOnly,
  rejtett = [],
}: {
  record: Record<string, unknown>;
  fieldTypes: Record<string, FieldTypeInfo> | null;
  visibleFields: string[] | null;
  patchPath: string;
  szekciok: SzekcioDef[];
  readOnly: boolean;
  /** Mezők, amik se szekcióban, se a régi adatok között ne jelenjenek meg
   * (pl. a fejlécben linkként látszó kapcsolatok). */
  rejtett?: string[];
}) {
  const osszes = toEditableDetailFields(record, [], visibleFields, fieldTypes);
  const kulcsSzerint = new Map(osszes.map((f) => [f.key, f]));
  const felhasznalt = new Set<string>([...SOSE, ...rejtett]);

  const sections: DetailSection[] = [];
  for (const sz of szekciok) {
    if (sz.lathato === false) continue;
    const mezok: EditableDetailField[] = [];
    for (const d of sz.mezok) {
      const key = typeof d === "string" ? d : d.key;
      felhasznalt.add(key);
      const f = kulcsSzerint.get(key);
      if (!f) continue;
      mezok.push(typeof d === "string" ? f : { ...f, label: d.label });
    }
    if (mezok.length === 0 && !sz.extra) continue;
    sections.push({
      key: sz.key,
      label: sz.cim,
      content: (
        <Card title={sz.cim}>
          {mezok.length > 0 && <EditableDetailGrid patchPath={patchPath} fields={mezok} layout="boxed" readOnly={readOnly} />}
          {sz.extra && <div className={mezok.length > 0 ? "mt-5 border-t border-border pt-5" : ""}>{sz.extra}</div>}
        </Card>
      ),
    });
  }

  const regi = osszes.filter((f) => !felhasznalt.has(f.key) && !ures(f));

  return (
    <div className="space-y-6">
      <DetailSections sections={sections} />
      {regi.length > 0 && (
        <details className="group rounded-[var(--radius-lg)] border border-border bg-surface-2 px-5 py-3">
          <summary className="cursor-pointer select-none text-[13px] text-text-muted hover:text-text-secondary">
            Régi adatok ({regi.length}) - a Notionből átjött, ritkán használt mezők
          </summary>
          <div className="mt-4">
            <EditableDetailGrid patchPath={patchPath} fields={regi} readOnly />
          </div>
        </details>
      )}
    </div>
  );
}

export type Jelveny = { label: string; tone: "success" | "warning" | "danger" | "neutral" | "accent" | "blue" | "teal" | "orange" | "pink" };

/** Az adatlap fejléce: cím, a fő összeg nagyban, alatta a részletek, a
 * legfontosabb állapotok jelvényként és a kapcsolódó rekordok linkjei. */
export function AdatlapFej({
  cim,
  felirat,
  osszeg,
  osszegAlatt,
  jelvenyek,
  linkek,
}: {
  cim: string;
  /** Kis felirat a cím fölött (pl. „Kiadás”). */
  felirat: string;
  osszeg: string | null;
  osszegAlatt?: string | null;
  jelvenyek: Jelveny[];
  linkek: { href: string; label: string }[];
}) {
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="min-w-0">
          <p className="t-label mb-1">{felirat}</p>
          <h1 className="break-words text-[22px] font-semibold leading-tight text-text-primary">{cim}</h1>
          {jelvenyek.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {jelvenyek.map((j) => (
                <StatusBadge key={j.label} label={j.label} tone={j.tone} />
              ))}
            </div>
          )}
          {linkek.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
              {linkek.map((l) => (
                <a key={l.href} href={l.href} className="text-text-accent hover:underline">
                  {l.label}
                </a>
              ))}
            </div>
          )}
        </div>
        {osszeg && (
          <div className="text-right">
            <p className="font-mono text-[26px] font-semibold tabular-nums text-text-primary">{osszeg}</p>
            {osszegAlatt && <p className="mt-0.5 text-[12.5px] text-text-muted">{osszegAlatt}</p>}
          </div>
        )}
      </div>
    </Card>
  );
}
