"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { DeleteButton } from "@/components/DeleteButton";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { M2mLinker } from "@/components/M2mLinker";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { ALLAPOT_CIMKE, KESZ_ALLAPOT, hataridoJelzes } from "@/components/hype-todo/hatarido";
import type { Employee, HypeTodoItem } from "@/lib/api";
import { napKulonbseg } from "@/lib/idoszak";

// Nem a lib/api.ts-ből importáljuk ezeket (bár csak sima konstansok/
// függvények) - az a modul a next/headers-t is behúzza (szerver-oldali
// cookie-olvasáshoz), és egy kliens-komponensbe akár csak egyetlen NEM
// type-only importja is beviszi a teljes modult, ami build hibát okoz.
const HYPE_TODO_BASE_PATH = "/api/v1/hype-todo";

type Nezet = "allapot" | "hatarido";
type Gyors = "" | "lejart" | "het" | "ellenorzes" | "felelos_nelkul";

/** Állapot szerinti csoportok sorrendje: ami épp megy, ami vár, ami
 * ellenőrzésre vár - a kész feladatok külön fülön. */
const ALLAPOT_CSOPORTOK: { kulcs: string; cim: string; pont: string; illik: (a: string | null) => boolean }[] = [
  { kulcs: "folyamatban", cim: "Folyamatban", pont: "bg-text-accent", illik: (a) => a === "In progress" },
  { kulcs: "nincs", cim: "Nincs elkezdve", pont: "bg-text-muted", illik: (a) => a === "Not started" },
  { kulcs: "ellenorzes", cim: "Ellenőrzésre vár", pont: "bg-text-warning", illik: (a) => a === "Ellenőrzés" },
  {
    kulcs: "egyeb",
    cim: "Állapot nélkül",
    pont: "bg-surface-3",
    illik: (a) => !a || !["In progress", "Not started", "Ellenőrzés", KESZ_ALLAPOT].includes(a),
  },
];

const TONE_SZOVEG: Record<string, string> = {
  danger: "text-text-danger",
  warning: "text-text-warning",
  neutral: "text-text-secondary",
  success: "text-text-success",
};

function rendez(a: HypeTodoItem, b: HypeTodoItem): number {
  // Határidő szerint előre (a határidő nélküliek a végén), azon belül a legújabb elöl.
  if (a.hatarido && b.hatarido) return a.hatarido < b.hatarido ? -1 : a.hatarido > b.hatarido ? 1 : b.id - a.id;
  if (a.hatarido) return -1;
  if (b.hatarido) return 1;
  return b.id - a.id;
}

/** A HYPE TO-DO LIST (a felhasználó kérése, 2026-10: jobban tagolt,
 * átláthatóbb): felül összesítő (lejárt, egy héten belül, ellenőrzésre vár,
 * felelős nélkül - kattintva szűr), alatta kereső és szűrők, a feladatok pedig
 * ÁLLAPOT vagy HATÁRIDŐ szerint csoportosítva, csoportonként összecsukhatóan.
 * Egy sor: cím (a feladat oldalára visz), alatta kategória, ellenőrző és a
 * leírás eleje; jobbra a felelősök, a határidő (emberi alakban: „holnap”,
 * „3 napja lejárt”) és az állapot - ezek helyben is szerkeszthetők. */
export function HypeTodoContent({
  items,
  employees,
  assignableEmployees,
  statusOptions,
  kategoriaOptions,
  canCreate,
  canDelete,
  canEdit,
  ma,
}: {
  items: HypeTodoItem[];
  employees: Employee[];
  /** Csak azok, akik ténylegesen látják ezt az oldalt (lásd
   * getLathatjakAzOldalt) - Felelősnek ÚJ hozzárendelésre csak ők
   * választhatók. Egy már hozzárendelt, de időközben jogosultságot vesztett
   * ember neve továbbra is látszik (lásd felelosOptions), csak eltávolítani
   * lehet, újra hozzáadni nem. */
  assignableEmployees: Employee[];
  statusOptions: string[];
  kategoriaOptions: string[];
  canCreate: boolean;
  canDelete: boolean;
  canEdit: boolean;
  /** A mai nap Budapesten (YYYY-MM-DD) - a szerver adja, hogy egyezzen. */
  ma: string;
}) {
  const [tab, setTab] = useState<"aktiv" | "kesz">("aktiv");
  const [nezet, setNezet] = useState<Nezet>("allapot");
  const [gyors, setGyors] = useState<Gyors>("");
  const [q, setQ] = useState("");
  const [kategoria, setKategoria] = useState("");
  const [felelos, setFelelos] = useState("");
  const [csukott, setCsukott] = useState<Set<string>>(new Set());
  const employeeName = useMemo(() => new Map(employees.map((e) => [e.id, e.full_name])), [employees]);
  const assignableIds = useMemo(() => new Set(assignableEmployees.map((e) => e.id)), [assignableEmployees]);

  const aktivak = items.filter((i) => i.allapot !== KESZ_ALLAPOT);
  const keszek = items.filter((i) => i.allapot === KESZ_ALLAPOT);

  const lejart = (i: HypeTodoItem) => !!i.hatarido && napKulonbseg(ma, i.hatarido) < 0;
  const hetenBelul = (i: HypeTodoItem) => !!i.hatarido && napKulonbseg(ma, i.hatarido) >= 0 && napKulonbseg(ma, i.hatarido) <= 7;
  const osszesito: { kulcs: Gyors; cim: string; db: number; tone: string }[] = [
    { kulcs: "lejart", cim: "Lejárt", db: aktivak.filter(lejart).length, tone: "text-text-danger" },
    { kulcs: "het", cim: "7 napon belül", db: aktivak.filter(hetenBelul).length, tone: "text-text-warning" },
    { kulcs: "ellenorzes", cim: "Ellenőrzésre vár", db: aktivak.filter((i) => i.allapot === "Ellenőrzés").length, tone: "text-text-primary" },
    { kulcs: "felelos_nelkul", cim: "Felelős nélkül", db: aktivak.filter((i) => i.felelos_employee_ids.length === 0).length, tone: "text-text-primary" },
  ];

  const felelosValasztek = useMemo(() => {
    const idk = new Set(items.flatMap((i) => i.felelos_employee_ids));
    return employees.filter((e) => idk.has(e.id)).sort((a, b) => a.full_name.localeCompare(b.full_name, "hu"));
  }, [items, employees]);

  const qn = q.trim().toLowerCase();
  const szurt = (tab === "aktiv" ? aktivak : keszek).filter((i) => {
    if (qn && !`${i.feladat} ${i.leiras ?? ""}`.toLowerCase().includes(qn)) return false;
    if (kategoria === "-" ? i.kategoria : kategoria && i.kategoria !== kategoria) return false;
    if (felelos === "-" ? i.felelos_employee_ids.length > 0 : felelos && !i.felelos_employee_ids.includes(Number(felelos)))
      return false;
    if (tab === "aktiv") {
      if (gyors === "lejart" && !lejart(i)) return false;
      if (gyors === "het" && !hetenBelul(i)) return false;
      if (gyors === "ellenorzes" && i.allapot !== "Ellenőrzés") return false;
      if (gyors === "felelos_nelkul" && i.felelos_employee_ids.length > 0) return false;
    }
    return true;
  });

  const csoportok: { kulcs: string; cim: string; pont: string; tetelek: HypeTodoItem[] }[] =
    tab === "kesz"
      ? [{ kulcs: "kesz", cim: "Kész feladatok", pont: "bg-text-success", tetelek: [...szurt].sort((a, b) => -rendez(a, b)) }]
      : nezet === "allapot"
        ? ALLAPOT_CSOPORTOK.map((c) => ({ ...c, tetelek: szurt.filter((i) => c.illik(i.allapot)).sort(rendez) }))
        : [
            { kulcs: "lejart", cim: "Lejárt", pont: "bg-text-danger", tetelek: szurt.filter(lejart) },
            { kulcs: "het", cim: "A következő 7 napban", pont: "bg-text-warning", tetelek: szurt.filter(hetenBelul) },
            {
              kulcs: "kesobb",
              cim: "Később",
              pont: "bg-text-accent",
              tetelek: szurt.filter((i) => !!i.hatarido && napKulonbseg(ma, i.hatarido) > 7),
            },
            { kulcs: "nincs_hatarido", cim: "Nincs határidő", pont: "bg-text-muted", tetelek: szurt.filter((i) => !i.hatarido) },
          ].map((c) => ({ ...c, tetelek: c.tetelek.sort(rendez) }));

  function felelosOptions(item: HypeTodoItem) {
    const marHozzarendelt = new Set(item.felelos_employee_ids);
    return employees
      .filter((e) => assignableIds.has(e.id) || marHozzarendelt.has(e.id))
      .map((e) => ({ id: e.id, label: e.full_name }));
  }

  function felelosNevek(item: HypeTodoItem): string {
    const nevek = item.felelos_employee_ids.map((id) => employeeName.get(id)).filter((n): n is string => !!n);
    return nevek.length > 0 ? nevek.join(", ") : "–";
  }

  function csukas(kulcs: string) {
    setCsukott((c) => {
      const u = new Set(c);
      if (u.has(kulcs)) u.delete(kulcs);
      else u.add(kulcs);
      return u;
    });
  }

  const szuroAktiv = !!(qn || kategoria || felelos || gyors);
  const gomb = (aktiv: boolean) =>
    `rounded-[var(--radius)] px-3 py-1.5 text-[13px] ${aktiv ? "bg-surface-3 text-text-primary" : "text-text-secondary hover:bg-surface-3"}`;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="t-page">HYPE TO-DO LIST</h1>
          <p className="mt-1 text-[13px] text-text-muted">
            {aktivak.length} nyitott · {keszek.length} kész feladat
          </p>
        </div>
      </div>

      {/* Összesítő - kattintva szűr (újra kattintva visszavonja). */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {osszesito.map((o) => {
          const aktiv = tab === "aktiv" && gyors === o.kulcs;
          return (
            <button
              key={o.kulcs}
              type="button"
              aria-pressed={aktiv}
              onClick={() => {
                setTab("aktiv");
                setGyors(aktiv ? "" : o.kulcs);
              }}
              className={`rounded-[var(--radius-lg)] border px-4 py-3 text-left transition-colors ${
                aktiv ? "border-text-accent bg-surface-3" : "border-border bg-surface-2 hover:bg-surface-3"
              }`}
            >
              <p className="t-label">{o.cim}</p>
              <p className={`mt-1 text-[24px] font-semibold tabular-nums ${o.db > 0 ? o.tone : "text-text-muted"}`}>{o.db}</p>
            </button>
          );
        })}
      </div>

      {canCreate && (
        <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-3">
          <QuickCreateForm
            postPath={HYPE_TODO_BASE_PATH}
            addLabel="+ Új feladat hozzáadása"
            fields={[
              { name: "feladat", label: "Feladat", required: true },
              { name: "hatarido", label: "Határidő", type: "date" },
            ]}
          />
        </div>
      )}

      {/* Fülek, nézet és szűrők egy sorban. */}
      <div className="flex flex-col gap-3 rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setTab("aktiv")} className={gomb(tab === "aktiv")}>
            Nyitott ({aktivak.length})
          </button>
          <button type="button" onClick={() => setTab("kesz")} className={gomb(tab === "kesz")}>
            Kész ({keszek.length})
          </button>
          {tab === "aktiv" && (
            <>
              <span className="mx-1 hidden h-5 w-px bg-border sm:inline-block" />
              <span className="text-[12px] text-text-muted">Csoportosítás:</span>
              <button type="button" onClick={() => setNezet("allapot")} className={gomb(nezet === "allapot")}>
                Állapot
              </button>
              <button type="button" onClick={() => setNezet("hatarido")} className={gomb(nezet === "hatarido")}>
                Határidő
              </button>
            </>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Keresés a feladatban, leírásban…"
            className="w-full rounded-[var(--radius)] border border-border bg-surface-3 px-2.5 py-1.5 text-[13px] text-text-primary focus:outline-none sm:w-[280px]"
          />
          <select
            value={kategoria}
            onChange={(e) => setKategoria(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-secondary"
            aria-label="Kategória"
          >
            <option value="">Minden kategória</option>
            {kategoriaOptions.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
            <option value="-">Kategória nélkül</option>
          </select>
          <select
            value={felelos}
            onChange={(e) => setFelelos(e.target.value)}
            className="rounded-[var(--radius)] border border-border bg-surface-3 px-2 py-1.5 text-[13px] text-text-secondary"
            aria-label="Felelős"
          >
            <option value="">Minden felelős</option>
            {felelosValasztek.map((e) => (
              <option key={e.id} value={e.id}>
                {e.full_name}
              </option>
            ))}
            <option value="-">Felelős nélkül</option>
          </select>
          {szuroAktiv && (
            <button
              type="button"
              onClick={() => {
                setQ("");
                setKategoria("");
                setFelelos("");
                setGyors("");
              }}
              className="text-[12.5px] text-text-accent hover:underline"
            >
              Szűrők törlése
            </button>
          )}
          <span className="ml-auto text-[12px] text-text-muted">{szurt.length} találat</span>
        </div>
      </div>

      {szurt.length === 0 ? (
        <p className="rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-8 text-center text-[13px] text-text-muted">
          {items.length === 0 ? "Még nincs felvett feladat." : "Nincs a szűrőknek megfelelő feladat."}
        </p>
      ) : (
        csoportok
          .filter((c) => c.tetelek.length > 0)
          .map((c) => {
            const csukva = csukott.has(c.kulcs);
            return (
              <section key={c.kulcs} className="overflow-hidden rounded-[var(--radius-lg)] border border-border bg-surface-2">
                <button
                  type="button"
                  onClick={() => csukas(c.kulcs)}
                  aria-expanded={!csukva}
                  className="flex w-full items-center gap-2.5 border-b border-border px-4 py-2.5 text-left hover:bg-surface-3"
                >
                  <span className={`inline-block h-2.5 w-2.5 rounded-full ${c.pont}`} />
                  <span className="text-[14px] font-semibold text-text-primary">{c.cim}</span>
                  <span className="rounded-full bg-surface-3 px-2 text-[12px] tabular-nums text-text-secondary">{c.tetelek.length}</span>
                  <span className="ml-auto text-[12px] text-text-muted">{csukva ? "▸ kinyit" : "▾"}</span>
                </button>
                {!csukva && (
                  <>
                    <div className="hidden grid-cols-[minmax(0,1fr)_220px_150px_150px_28px] gap-4 border-b border-border px-4 py-1.5 text-[11.5px] uppercase tracking-wide text-text-muted md:grid">
                      <span>Feladat</span>
                      <span>Felelős</span>
                      <span>Határidő</span>
                      <span>Állapot</span>
                      <span />
                    </div>
                    <ul className="divide-y divide-border">
                      {c.tetelek.map((t) => {
                        const path = `${HYPE_TODO_BASE_PATH}/${t.id}`;
                        const h = hataridoJelzes(t.hatarido, ma, t.allapot === KESZ_ALLAPOT);
                        const ellenorzo = t.ellenorzes_felelos_id ? employeeName.get(t.ellenorzes_felelos_id) : null;
                        return (
                          <li
                            key={t.id}
                            className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-[minmax(0,1fr)_220px_150px_150px_28px] md:items-start md:gap-4"
                          >
                            <div className="min-w-0">
                              <Link
                                href={`/hype-todo-lista/${t.id}`}
                                className="block break-words text-[14px] font-medium text-text-primary hover:text-text-accent"
                              >
                                {t.feladat}
                              </Link>
                              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-text-muted">
                                {canEdit ? (
                                  <EditableStatusBadge
                                    patchPath={path}
                                    field="kategoria"
                                    value={t.kategoria}
                                    options={kategoriaOptions}
                                    placeholder="Nincs kategória"
                                  />
                                ) : (
                                  t.kategoria && <span>{t.kategoria}</span>
                                )}
                                {ellenorzo && <span>Ellenőrzi: {ellenorzo}</span>}
                                {t.csatolando_link && <span title="Van csatolt link">🔗 link</span>}
                              </div>
                              {t.leiras && <p className="mt-1 line-clamp-1 text-[12.5px] text-text-secondary">{t.leiras}</p>}
                            </div>
                            <div className="text-[13px] text-text-secondary">
                              <span className="t-label mr-2 md:hidden">Felelős</span>
                              {canEdit ? (
                                <M2mLinker
                                  patchPath={path}
                                  fieldName="felelos_employee_ids"
                                  currentIds={t.felelos_employee_ids}
                                  options={felelosOptions(t)}
                                  addLabel="Hozzáadás"
                                  emptyText="Nincs felelős."
                                  azonnal
                                />
                              ) : (
                                felelosNevek(t)
                              )}
                            </div>
                            <div className="flex flex-wrap items-start gap-x-4 gap-y-2 md:contents">
                              <div className="text-[13px]">
                                <span className="t-label mr-2 md:hidden">Határidő</span>
                                {canEdit ? (
                                  <EditableTableCell patchPath={path} field="hatarido" value={t.hatarido} type="date" placeholder="Nincs" />
                                ) : (
                                  <span className="text-text-secondary">{t.hatarido ?? "–"}</span>
                                )}
                                {h && h.tone !== "neutral" && <p className={`mt-0.5 text-[12px] ${TONE_SZOVEG[h.tone]}`}>{h.szoveg}</p>}
                              </div>
                              <div>
                                <EditableStatusBadge
                                  patchPath={path}
                                  field="allapot"
                                  value={t.allapot}
                                  options={statusOptions}
                                  labels={ALLAPOT_CIMKE}
                                />
                              </div>
                              <div className="ml-auto flex md:ml-0 md:justify-end">
                                {canDelete && <DeleteButton path={path} />}
                              </div>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </>
                )}
              </section>
            );
          })
      )}
    </div>
  );
}
