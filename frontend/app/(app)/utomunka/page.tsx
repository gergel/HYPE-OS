import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { DeliverableBoard, type BoardCard, type BoardColumn } from "@/components/deliverable/DeliverableBoard";
import { ForgatasokCalendar } from "@/components/deliverable/ForgatasokCalendar";
import { UtomunkaViewTabs } from "@/components/deliverable/UtomunkaViewTabs";
import {
  Deliverable,
  ENTITY_PATHS,
  formatDate,
  getDeliverables,
  getEmployees,
  getFieldTypes,
  getProjects,
  getVinyoOptions,
} from "@/lib/api";

const NO_STATUS_KEY = "__nincs_allapot__";

/** Az Utómunka oldal két nézetet ad: egy "Vágó nézetet" (állapot szerinti
 * tábla + forgatások naptár + vinyó szerinti tábla - hogy a vágóknak ne a
 * nyers adattáblát kelljen böngészniük), és a régi "Admin listát" (a teljes
 * DataTable, szűréssel/rendezéssel/törléssel). */
export default async function UtomunkaPage() {
  const [deliverables, employees, projects, fieldTypes, vinyoOptions] = await Promise.all([
    getDeliverables(),
    getEmployees(),
    getProjects(),
    getFieldTypes("deliverable"),
    getVinyoOptions(),
  ]);

  const employeeName = new Map(employees.map((e) => [e.id, e.full_name]));

  function toCard(d: Deliverable, badges: string[]): BoardCard {
    const subtitleParts = [
      d.hatarido ? `Határidő: ${formatDate(d.hatarido)}` : null,
      d.assigned_to_employee_id ? `Kiosztva: ${employeeName.get(d.assigned_to_employee_id) ?? "?"}` : null,
    ].filter((p): p is string => p !== null);
    return {
      id: d.id,
      href: `/utomunka/${d.id}`,
      title: d.projekt_neve,
      subtitle: subtitleParts.length > 0 ? subtitleParts.join(" · ") : null,
      badges,
    };
  }

  // --- Állapot szerinti tábla ---
  const statusOptions = fieldTypes.allapot?.options ?? [];
  const byStatus = new Map<string, Deliverable[]>();
  for (const d of deliverables) {
    const key = d.allapot && statusOptions.includes(d.allapot) ? d.allapot : NO_STATUS_KEY;
    if (!byStatus.has(key)) byStatus.set(key, []);
    byStatus.get(key)!.push(d);
  }
  const statusColumns: BoardColumn[] = [
    ...statusOptions.map((s) => ({ key: s, label: s, cards: (byStatus.get(s) ?? []).map((d) => toCard(d, d.vinyok ?? [])) })),
    ...(byStatus.has(NO_STATUS_KEY)
      ? [{ key: NO_STATUS_KEY, label: "Nincs állapot", cards: byStatus.get(NO_STATUS_KEY)!.map((d) => toCard(d, d.vinyok ?? [])) }]
      : []),
  ];

  // --- Vinyó szerinti tábla ---
  const byVinyo = new Map<string, Deliverable[]>();
  for (const d of deliverables) {
    for (const v of d.vinyok ?? []) {
      if (!byVinyo.has(v)) byVinyo.set(v, []);
      byVinyo.get(v)!.push(d);
    }
  }
  const vinyoColumns: BoardColumn[] = vinyoOptions
    .filter((v) => (byVinyo.get(v)?.length ?? 0) > 0)
    .map((v) => ({
      key: v,
      label: v,
      cards: byVinyo.get(v)!.map((d) => toCard(d, d.allapot ? [d.allapot] : [])),
    }));

  const calendarProjects = projects
    .filter((p) => p.forgatas_datuma !== null)
    .map((p) => ({ id: p.id, nev: p.nev, forgatas_datuma: p.forgatas_datuma }));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <UtomunkaViewTabs
          board={
            <div className="space-y-6">
              <Card title="Állapot szerint">
                <DeliverableBoard columns={statusColumns} />
              </Card>
              <Card title="Forgatások naptár">
                <ForgatasokCalendar projects={calendarProjects} />
              </Card>
              <Card title="Vinyók szerint">
                <DeliverableBoard columns={vinyoColumns} />
              </Card>
            </div>
          }
          list={
            <Card title={`Utómunka (${deliverables.length})`}>
              <DataTable<Deliverable>
                rows={deliverables}
                emptyText="Még nincs felvett vágandó anyag - importáld a Notionból, vagy adj hozzá egyet a /api/v1/deliverables végponton."
                getHref={(d) => `/utomunka/${d.id}`}
                deleteHref={(d) => `${ENTITY_PATHS.deliverable}/${d.id}`}
                filterable
                columns={[
                  { header: "Anyag", render: (d) => d.projekt_neve, sortAccessor: (d) => d.projekt_neve },
                  {
                    header: "Állapot",
                    render: (d) => (d.allapot ? <StatusBadge label={d.allapot} tone="neutral" /> : "–"),
                    sortAccessor: (d) => d.allapot,
                  },
                  { header: "Határidő", render: (d) => formatDate(d.hatarido), sortAccessor: (d) => d.hatarido },
                  {
                    header: "Kiküldve",
                    align: "right",
                    render: (d) => (
                      <StatusBadge label={d.anyag_kikuldve ? "Kiküldve" : "Nincs kiküldve"} tone={d.anyag_kikuldve ? "success" : "warning"} />
                    ),
                    sortAccessor: (d) => (d.anyag_kikuldve ? 1 : 0),
                  },
                ]}
              />
            </Card>
          }
        />
      </div>
    </div>
  );
}
