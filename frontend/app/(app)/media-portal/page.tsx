import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { MediaPortalCreatePanel } from "@/components/media-portal-admin/MediaPortalCreatePanel";
import { MediaPortalMaintenancePanel } from "@/components/media-portal-admin/MediaPortalMaintenancePanel";
import { getPortals, getProjects } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = { draft: "Vázlat", live: "Élő", archived: "Archivált" };
const STATUS_TONE: Record<string, "neutral" | "success" | "warning"> = {
  draft: "neutral",
  live: "success",
  archived: "warning",
};

export default async function MediaPortalPage() {
  const [portals, projects] = await Promise.all([getPortals(), getProjects()]);
  const linkedProjectIds = new Set(portals.map((p) => p.project_id));
  const availableProjects = projects.filter((p) => !linkedProjectIds.has(p.id));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-4 p-6">
        <Card title="Új Portál létrehozása">
          <MediaPortalCreatePanel projects={availableProjects} />
        </Card>
        <Card title={`Média Portálok (${portals.length})`}>
          <DataTable
            rows={portals}
            emptyText="Még nincs létrehozott Portál - válassz egy projektet fent."
            getHref={(p) => `/media-portal/${p.id}`}
            deleteHref={(p) => `/api/v1/portal-admin/${p.id}`}
            filterable
            columns={[
              { header: "Cím", render: (p) => p.title, sortAccessor: (p) => p.title },
              { header: "Ügyfél", render: (p) => p.client_name || "–", sortAccessor: (p) => p.client_name },
              { header: "Slug", render: (p) => p.slug, sortAccessor: (p) => p.slug },
              {
                header: "Állapot",
                render: (p) => <StatusBadge label={STATUS_LABEL[p.status] ?? p.status} tone={STATUS_TONE[p.status] ?? "neutral"} />,
                sortAccessor: (p) => p.status,
              },
              {
                header: "Jelszó",
                render: (p) => (p.has_password ? "Van" : "Nincs"),
                sortAccessor: (p) => (p.has_password ? 1 : 0),
              },
              { header: "Lejárat", render: (p) => p.expires_at ?? "–", sortAccessor: (p) => p.expires_at },
            ]}
          />
        </Card>
        <Card title="Karbantartás">
          <MediaPortalMaintenancePanel />
        </Card>
      </div>
    </div>
  );
}
