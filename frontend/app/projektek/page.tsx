import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { formatDate, getProjectCodes, getProjects, Project } from "@/lib/api";

export default async function ProjektekPage() {
  const [projects, projectCodes] = await Promise.all([getProjects(), getProjectCodes()]);
  const projectCodeById = new Map(projectCodes.map((pc) => [pc.id, pc.projektkod]));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Projektek (${projects.length})`}>
          <DataTable<Project>
            rows={projects}
            emptyText="Még nincs felvett projekt - importáld a Notionból, vagy adj hozzá egyet a /api/v1/projects végponton."
            getHref={(p) => `/projektek/${p.id}`}
            columns={[
              { header: "Név", render: (p) => p.nev },
              { header: "Projektkód", render: (p) => projectCodeById.get(p.project_code_id) ?? "–" },
              { header: "Forgatás dátuma", render: (p) => formatDate(p.forgatas_datuma) },
              { header: "Helyszín", render: (p) => p.helyszin ?? "–" },
              { header: "Állapot", render: (p) => (p.allapot ? <StatusBadge label={p.allapot} tone="neutral" /> : "–") },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
