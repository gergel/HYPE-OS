import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DetailSections } from "@/components/DetailSections";
import { EmployeeFkPicker } from "@/components/EmployeeFkPicker";
import { KommentChat } from "@/components/KommentChat";
import { M2mLinker } from "@/components/M2mLinker";
import { ReadOnlyDetailField } from "@/components/ReadOnlyDetailField";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getDetailTabs,
  getEmployees,
  getFieldTypes,
  getHypeTodoKommentek,
  getLathatjakAzOldalt,
  getMyPagePermissions,
  getRecord,
  getVisibleFields,
} from "@/lib/api";
import { buildFieldTabs } from "@/lib/detailTabs";

const PAGE = "/hype-todo-lista";
const FELELOSOK_WIDGET_KEY = "felelos_employee_ids";
const ELLENORZES_FELELOS_KEY = "ellenorzes_felelos_id";
//: Egyszemélyes idegenkulcs-mezők, amiket a rendszer AUTOMATIKUSAN tölt ki
//: (lásd backend routes/hype_todo.py: a létrehozó, illetve aki
//: Ellenőrzés/Done állapotba teszi) - a generikus mezőrács ezeket nyers
//: számként (id) mutatná; itt NÉVRE feloldva, csak olvashatóként jelenítjük
//: meg (lásd components/ReadOnlyDetailField.tsx). Az "Ellenőrzés felelős"
//: nincs köztük: az kézzel választható (lásd lent, EmployeeFkPicker).
const SZEMELY_MEZOK: { key: "aki_felvezette_id" | "aki_ellenorizte_id"; label: string }[] = [
  { key: "aki_felvezette_id", label: "Aki felvezette" },
  { key: "aki_ellenorizte_id", label: "Aki ellenőrizte/készbe rakta" },
];

export default async function HypeTodoDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const itemId = Number(id);
  const [item, visibleFields, fieldTypes, dbTabs, pagePermissions, employees, lathatjakIds, kommentek] =
    await Promise.all([
      getRecord(ENTITY_PATHS.hypeTodo, itemId),
      getVisibleFields("hypeTodo"),
      getFieldTypes("hypeTodo"),
      getDetailTabs("hypeTodo"),
      getMyPagePermissions(),
      getEmployees(),
      getLathatjakAzOldalt(PAGE),
      getHypeTodoKommentek(itemId),
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
  // Az Ellenőrzés felelős ugyanazzal a szűréssel választható, mint a Felelős:
  // csak aki látja az oldalt - a már beállított, de jogosultságot vesztett
  // ember neve viszont látszik (csak leváltani lehet, újra kiválasztani nem).
  const ellenorzesFelelosId = (item[ELLENORZES_FELELOS_KEY] as number | null) ?? null;
  const ellenorzesFelelosOptions = employees
    .filter((e) => lathatjakSet.has(e.id) || e.id === ellenorzesFelelosId)
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
    alwaysHidden: [FELELOSOK_WIDGET_KEY, ELLENORZES_FELELOS_KEY, ...SZEMELY_MEZOK.map((m) => m.key)],
    widgets: {
      [FELELOSOK_WIDGET_KEY]: (
        <M2mLinker
          patchPath={patchPath}
          fieldName="felelos_employee_ids"
          currentIds={currentIds}
          options={felelosOptions}
          addLabel="Felelős hozzáadása"
          emptyText="Nincs felelős hozzárendelve."
          azonnal
        />
      ),
      [ELLENORZES_FELELOS_KEY]: (
        <div className="flex flex-col gap-1.5">
          <span className="t-label">Ellenőrzés felelős</span>
          <EmployeeFkPicker
            patchPath={patchPath}
            field={ELLENORZES_FELELOS_KEY}
            currentId={ellenorzesFelelosId}
            options={ellenorzesFelelosOptions}
            emptyLabel="Nincs kijelölve"
          />
        </div>
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

        {/* Hozzászólások - a Notion-import a feladat Notion-beli kommentjeit
            is ide hozza (lásd backend notion_import/importers_wave4.import_hype_todo). */}
        <Card title="Hozzászólások">
          <KommentChat
            endpoint={`/api/v1/hype-todo/${itemId}/comments`}
            topic={`hypeTodoComments:${itemId}`}
            initialComments={kommentek}
            mentionableEmployees={employees.map((e) => ({ id: e.id, full_name: e.full_name }))}
          />
        </Card>
      </div>
    </div>
  );
}
