import Link from "next/link";
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
      {/* ANYAGBEKÉRÉSEK (a felhasználó kérése): a nyersanyag-bekérő és
          kreatív brief nézet a portálok mellett él, saját aloldalon. */}
      <div className="flex items-center gap-3 px-4 pt-4 md:px-8">
        <Link
          href="/media-portal/anyagbekeresek"
          className="rounded-[var(--radius)] border border-border px-3 py-1.5 text-[13px] text-text-secondary hover:bg-surface-3"
        >
          Anyagbekérések →
        </Link>
      </div>
      <MediaPortalDashboard initialPortals={portals} availableProjects={availableProjects} />
    </div>
  );
}
