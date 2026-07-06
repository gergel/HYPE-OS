import { TopBar } from "@/components/TopBar";
import { MediaPortalDashboard } from "@/components/media-portal-admin/MediaPortalDashboard";
import { getPortals, getProjects } from "@/lib/api";

export default async function MediaPortalPage() {
  const [portals, projects] = await Promise.all([getPortals(), getProjects()]);
  const linkedProjectIds = new Set(portals.map((p) => p.project_id));
  const availableProjects = projects.filter((p) => !linkedProjectIds.has(p.id));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <MediaPortalDashboard initialPortals={portals} availableProjects={availableProjects} />
    </div>
  );
}
