import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DeleteButton } from "@/components/DeleteButton";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { EmployeeFkPicker } from "@/components/EmployeeFkPicker";
import { KommentChat } from "@/components/KommentChat";
import { M2mLinker } from "@/components/M2mLinker";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { ALLAPOT_CIMKE, KESZ_ALLAPOT, hataridoJelzes } from "@/components/hype-todo/hatarido";
import {
  ENTITY_PATHS,
  getEmployees,
  getFieldTypes,
  getHypeTodoKommentek,
  getLathatjakAzOldalt,
  getMyPagePermissions,
  getRecord,
  getVisibleFields,
} from "@/lib/api";
import { toEditableDetailFields, type EditableDetailField } from "@/lib/detail";
import { budapestiMa } from "@/lib/idoszak";
import { canDoPageAction } from "@/lib/permissions";

const PAGE = "/hype-todo-lista";

//: A külön blokkban (fejléc, oldalsáv) megjelenő mezők - ezek nem kerülnek a
//: „További adatok” közé. Az egyszemélyes id-mezők (aki felvezette /
//: ellenőrizte) NÉVRE feloldva, csak olvashatóként látszanak; a rendszer
//: tölti ki őket (lásd backend routes/hype_todo.py).
const KULON_MEZOK = new Set([
  "id",
  "created_at",
  "updated_at",
  "feladat",
  "leiras",
  "csatolando_link",
  "allapot",
  "kategoria",
  "hatarido",
  "felelos_employee_ids",
  "ellenorzes_felelos_id",
  "aki_felvezette_id",
  "aki_ellenorizte_id",
  "letrehozas_idopontja",
]);

function ures(f: EditableDetailField): boolean {
  if (f.rawValue === null || f.rawValue === undefined || f.rawValue === "") {
    return f.value === null || f.value === undefined || f.value === "" || f.value === "–";
  }
  return false;
}

function datumIdo(v: unknown): string | null {
  if (typeof v !== "string" || !v) return null;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v.slice(0, 10);
  return d.toLocaleString("hu-HU", { timeZone: "Europe/Budapest", year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Egy HYPE TO-DO feladat adatlapja (a felhasználó kérése, 2026-10: rendezett,
 * átlátható): fejléc a címmel és a fő jelzésekkel (állapot, kategória,
 * határidő emberi alakban), alatta két oszlop - balra a feladat tartalma
 * (leírás, link) és a hozzászólások, jobbra a felelősök, az ellenőrzés és az
 * előzmények. A ritkán használt, máshol nem látszó mezők egy alapból csukott
 * „További adatok” blokkba kerülnek, hogy semmi ne vesszen el. */
export default async function HypeTodoDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const itemId = Number(id);
  const [item, visibleFields, fieldTypes, pagePermissions, employees, lathatjakIds, kommentek] = await Promise.all([
    getRecord(ENTITY_PATHS.hypeTodo, itemId),
    getVisibleFields("hypeTodo"),
    getFieldTypes("hypeTodo"),
    getMyPagePermissions(),
    getEmployees(),
    getLathatjakAzOldalt(PAGE),
    getHypeTodoKommentek(itemId),
  ]);
  if (!item) notFound();

  const canEdit = canDoPageAction(pagePermissions, PAGE, "edit");
  const canDelete = canDoPageAction(pagePermissions, PAGE, "delete");
  const patchPath = `${ENTITY_PATHS.hypeTodo}/${item.id}`;
  const currentIds = Array.isArray(item.felelos_employee_ids) ? (item.felelos_employee_ids as number[]) : [];
  const employeeName = new Map(employees.map((e) => [e.id, e.full_name]));
  // Felelősnek / ellenőrzőnek csak az választható, aki ténylegesen látja ezt
  // az oldalt - a már hozzárendelt, de időközben jogosultságot vesztett ember
  // neve továbbra is megjelenik (lásd HypeTodoContent.tsx felelosOptions).
  const lathatjakSet = new Set(lathatjakIds);
  const felelosOptions = employees
    .filter((e) => lathatjakSet.has(e.id) || currentIds.includes(e.id))
    .map((e) => ({ id: e.id, label: e.full_name }));
  const ellenorzesFelelosId = (item.ellenorzes_felelos_id as number | null) ?? null;
  const ellenorzesFelelosOptions = employees
    .filter((e) => lathatjakSet.has(e.id) || e.id === ellenorzesFelelosId)
    .map((e) => ({ id: e.id, label: e.full_name }));
  const nev = (v: unknown) => (typeof v === "number" ? (employeeName.get(v) ?? `#${v}`) : null);

  const mezok = toEditableDetailFields(item, [], visibleFields, fieldTypes);
  const mezo = new Map(mezok.map((f) => [f.key, f]));
  const CIMKE: Record<string, string> = { feladat: "Feladat", leiras: "Leírás", csatolando_link: "Csatolt link" };
  const tartalomMezok = ["feladat", "leiras", "csatolando_link"]
    .map((k) => mezo.get(k))
    .filter((f): f is EditableDetailField => !!f)
    .map((f) => ({
      ...f,
      label: CIMKE[f.key] ?? f.label,
      wide: true,
      ...(f.key === "leiras" ? { inputType: "textarea" as const } : {}),
    }));
  const elozmenyek = [
    { cim: "Felvezette", ertek: nev(item.aki_felvezette_id) },
    { cim: "Létrehozva", ertek: datumIdo(item.letrehozas_idopontja) ?? datumIdo(item.created_at) },
    { cim: "Utoljára módosítva", ertek: datumIdo(item.updated_at) },
  ].filter((e) => e.ertek);
  const tovabbi = mezok.filter((f) => !KULON_MEZOK.has(f.key) && !ures(f));

  const allapot = (item.allapot as string | null) ?? null;
  const kesz = allapot === KESZ_ALLAPOT;
  const hatarido = (item.hatarido as string | null) ?? null;
  const h = hataridoJelzes(hatarido, budapestiMa(), kesz);
  const link = typeof item.csatolando_link === "string" && /^https?:\/\//.test(item.csatolando_link) ? item.csatolando_link : null;
  const statusOptions = fieldTypes.allapot?.options ?? [];
  const kategoriaOptions = fieldTypes.kategoria?.options ?? [];

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        <BackLink href="/hype-todo-lista" label="HYPE TO-DO LIST" />

        {/* Fejléc: cím + a fő jelzések. */}
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="t-label mb-1">HYPE TO-DO · #{item.id}</p>
              <h1 className="break-words text-[22px] font-semibold leading-tight text-text-primary">
                {String(item.feladat ?? `Feladat #${item.id}`)}
              </h1>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {canEdit ? (
                  <>
                    <EditableStatusBadge patchPath={patchPath} field="allapot" value={allapot} options={statusOptions} labels={ALLAPOT_CIMKE} />
                    <EditableStatusBadge
                      patchPath={patchPath}
                      field="kategoria"
                      value={(item.kategoria as string | null) ?? null}
                      options={kategoriaOptions}
                      placeholder="Nincs kategória"
                    />
                  </>
                ) : (
                  <>
                    {allapot && <StatusBadge label={ALLAPOT_CIMKE[allapot] ?? allapot} tone={kesz ? "success" : "accent"} />}
                    {typeof item.kategoria === "string" && <StatusBadge label={item.kategoria} />}
                  </>
                )}
                {h ? (
                  <StatusBadge label={`Határidő: ${h.szoveg}`} tone={h.tone} />
                ) : (
                  <StatusBadge label="Nincs határidő" />
                )}
              </div>
            </div>
            {canDelete && (
              <DeleteButton
                path={patchPath}
                redirectTo="/hype-todo-lista"
                label="Feladat törlése"
                className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:text-text-danger"
              />
            )}
          </div>
        </Card>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          {/* Bal oszlop: a feladat tartalma és a hozzászólások. */}
          <div className="min-w-0 space-y-6">
            <Card title="A feladat">
              <EditableDetailGrid patchPath={patchPath} fields={tartalomMezok} layout="boxed" readOnly={!canEdit} />
              {link && (
                <a
                  href={link}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-4 inline-block text-[13px] text-text-accent hover:underline"
                >
                  Csatolt link megnyitása ↗
                </a>
              )}
            </Card>

            {/* Hozzászólások - a Notion-import a feladat Notion-beli kommentjeit
                is ide hozza (lásd backend notion_import/importers_wave4.import_hype_todo). */}
            <Card title={`Hozzászólások${kommentek.length ? ` (${kommentek.length})` : ""}`}>
              <KommentChat
                endpoint={`/api/v1/hype-todo/${itemId}/comments`}
                topic={`hypeTodoComments:${itemId}`}
                initialComments={kommentek}
                mentionableEmployees={employees.map((e) => ({ id: e.id, full_name: e.full_name }))}
              />
            </Card>

            {tovabbi.length > 0 && (
              <details className="rounded-[var(--radius-lg)] border border-border bg-surface-2 px-5 py-3">
                <summary className="cursor-pointer select-none text-[13px] text-text-muted hover:text-text-secondary">
                  További adatok ({tovabbi.length})
                </summary>
                <div className="mt-4">
                  <EditableDetailGrid patchPath={patchPath} fields={tovabbi} readOnly={!canEdit} />
                </div>
              </details>
            )}
          </div>

          {/* Jobb oszlop: kik és mikor. */}
          <div className="space-y-6">
            <Card title="Felelősök">
              {canEdit ? (
                <M2mLinker
                  patchPath={patchPath}
                  fieldName="felelos_employee_ids"
                  currentIds={currentIds}
                  options={felelosOptions}
                  addLabel="Felelős hozzáadása"
                  emptyText="Nincs felelős hozzárendelve."
                  azonnal
                />
              ) : (
                <p className="text-[13px] text-text-secondary">
                  {currentIds.map((i) => employeeName.get(i)).filter(Boolean).join(", ") || "Nincs felelős hozzárendelve."}
                </p>
              )}
            </Card>

            <Card title="Határidő és ellenőrzés">
              <div className="flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <span className="t-label">Határidő</span>
                  {canEdit ? (
                    <div className="text-[13px]">
                      <EditableTableCell patchPath={patchPath} field="hatarido" value={hatarido} type="date" placeholder="Nincs határidő" />
                    </div>
                  ) : (
                    <span className="text-[13px] text-text-secondary">{hatarido ?? "–"}</span>
                  )}
                  {h && <span className={`text-[12px] ${h.tone === "danger" ? "text-text-danger" : h.tone === "warning" ? "text-text-warning" : "text-text-muted"}`}>{h.szoveg}</span>}
                </div>
                <div className="flex flex-col gap-1.5">
                  <span className="t-label">Ellenőrzés felelős</span>
                  {canEdit ? (
                    <EmployeeFkPicker
                      patchPath={patchPath}
                      field="ellenorzes_felelos_id"
                      currentId={ellenorzesFelelosId}
                      options={ellenorzesFelelosOptions}
                      emptyLabel="Nincs kijelölve"
                    />
                  ) : (
                    <span className="text-[13px] text-text-secondary">{nev(ellenorzesFelelosId) ?? "Nincs kijelölve"}</span>
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  <span className="t-label">Aki ellenőrizte / készbe rakta</span>
                  <span className="text-[13px] text-text-secondary">{nev(item.aki_ellenorizte_id) ?? "Még senki"}</span>
                </div>
              </div>
            </Card>

            <Card title="Előzmények">
              {elozmenyek.length === 0 ? (
                <p className="text-[13px] text-text-muted">Nincs rögzített előzmény.</p>
              ) : (
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[13px]">
                  {elozmenyek.map((e) => (
                    <div key={e.cim} className="contents">
                      <dt className="text-text-muted">{e.cim}</dt>
                      <dd className="text-text-secondary">{e.ertek}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
