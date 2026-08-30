import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { DetailSections } from "@/components/DetailSections";
import { M2mLinker } from "@/components/M2mLinker";
import { ReadOnlyDetailField } from "@/components/ReadOnlyDetailField";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getDetailTabs,
  getEmployees,
  getFieldTypes,
  getLathatjakAzOldalt,
  getMyPagePermissions,
  getRecord,
  getVisibleFields,
} from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";

const PAGE = "/hype-todo-lista";
const FELELOSOK_WIDGET_KEY = "felelos_employee_ids";
//: Egyszemélyes idegenkulcs-mezők - a generikus mezőrács ezeket nyers
//: számként (id) mutatná; itt NÉVRE feloldva, csak olvashatóként jelenítjük
//: meg (lásd components/ReadOnlyDetailField.tsx).
const SZEMELY_MEZOK: { key: "aki_felvezette_id" | "ellenorzes_felelos_id" | "aki_ellenorizte_id"; label: string }[] = [
  { key: "aki_felvezette_id", label: "Aki felvezette" },
  { key: "ellenorzes_felelos_id", label: "Ellenőrzés felelős" },
  { key: "aki_ellenorizte_id", label: "Aki ellenőrizte/készbe rakta" },
];

export default async function HypeTodoDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const itemId = Number(id);
  const [item, visibleFields, fieldTypes, dbTabs, pagePermissions, employees, lathatjakIds] = await Promise.all([
    getRecord(ENTITY_PATHS.hypeTodo, itemId),
    getVisibleFields("hypeTodo"),
    getFieldTypes("hypeTodo"),
    getDetailTabs("hypeTodo"),
    getMyPagePermissions(),
    getEmployees(),
    getLathatjakAzOldalt(PAGE),
  ]);
  if (!item) notFound();

  const patchPath = `${ENTITY_PATHS.hypeTodo}/${item.id}`;
  const currentIds = Array.isArray(item.felelos_employee_ids) ? (item.felelos_employee_ids as number[]) : [];
  const employeeName = new Map(employees.map((e) => [e.id, e.full_name]));
  // Felelősnek csak az választható, aki ténylegesen látja ezt az oldalt - a
  // már hozzárendelt, de időközben jogosultságot vesztett ember neve
  // továbbra is megjelenik (lásd HypeTodoContent.tsx felelosOptions).
  const lathatjakSet = new Set(lathatjakIds);
  const felelosOptions = employees
    .filter((e) => lathatjakSet.has(e.id) || currentIds.includes(e.id))
    .map((e) => ({ id: e.id, label: e.full_name }));

  const tabs = buildFieldTabs({
    page: PAGE,
    patchPath,
    record: item,
    dbTabs,
    visibleFields,
    fieldTypes,
    pagePermissions,
    // A "Felelős" (több munkatárs) nem sima mező, hanem M2M kapcsolat -
    // ezért kivesszük az általános mezőrácsból, és helyette az M2mLinker
    // widgetet illesztjük be, minta: components/ProjectDetailContent.tsx. Az
    // egyszemélyes id-mezőket (SZEMELY_MEZOK) is kivesszük, hogy ne nyers
    // számként jelenjenek meg.
    alwaysHidden: [FELELOSOK_WIDGET_KEY, ...SZEMELY_MEZOK.map((m) => m.key)],
    widgets: {
      [FELELOSOK_WIDGET_KEY]: (
        <M2mLinker
          patchPath={patchPath}
          fieldName="felelos_employee_ids"
          currentIds={currentIds}
          options={felelosOptions}
          addLabel="Felelős hozzáadása"
          emptyText="Nincs felelős hozzárendelve."
        />
      ),
      ...Object.fromEntries(
        SZEMELY_MEZOK.map(({ key, label }) => {
          const id = item[key] as number | null;
          return [key, <ReadOnlyDetailField key={key} label={label} value={id ? (employeeName.get(id) ?? `#${id}`) : null} />];
        }),
      ),
    },
  });

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <div className="space-y-2">
          <BackLink href="/hype-todo-lista" label="HYPE TO-DO LIST" />
          <h1 className="t-page">{String(item.feladat ?? `Feladat #${item.id}`)}</h1>
        </div>

        <DetailSections sections={tabs} />
      </div>
    </div>
  );
}
