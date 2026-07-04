import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, formatDate, formatHuf, getClients, getProjectCodes, ProjectCode } from "@/lib/api";

export default async function ProjectKodokPage() {
  const [projectCodes, clients] = await Promise.all([getProjectCodes(), getClients()]);
  const clientNameById = new Map(clients.map((c) => [c.id, c.nev]));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Project Code-ok (${projectCodes.length})`}>
          <DataTable<ProjectCode>
            rows={projectCodes}
            emptyText="Még nincs felvett Project Code - importáld a Notionból, vagy adj hozzá egyet a /api/v1/project-codes végponton."
            getHref={(pc) => `/projektek/project-kodok/${pc.id}`}
            deleteHref={(pc) => `${ENTITY_PATHS.projectCode}/${pc.id}`}
            filterable
            columns={[
              { header: "Projektkód", render: (pc) => pc.projektkod, sortAccessor: (pc) => pc.projektkod },
              {
                header: "Ügyfél",
                render: (pc) => clientNameById.get(pc.client_id) ?? "–",
                sortAccessor: (pc) => clientNameById.get(pc.client_id),
              },
              { header: "Dátum", render: (pc) => formatDate(pc.datum), sortAccessor: (pc) => pc.datum },
              {
                header: "Összes költség",
                align: "right",
                render: (pc) => formatHuf(pc.osszes_koltseg),
                sortAccessor: (pc) => pc.osszes_koltseg,
              },
              {
                header: "Becsült profit",
                align: "right",
                render: (pc) => formatHuf(pc.becsult_profit),
                sortAccessor: (pc) => pc.becsult_profit,
              },
              {
                header: "Státusz",
                align: "right",
                render: (pc) => (pc.esemeny_allapota ? <StatusBadge label={pc.esemeny_allapota} tone="neutral" /> : "–"),
                sortAccessor: (pc) => pc.esemeny_allapota,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
