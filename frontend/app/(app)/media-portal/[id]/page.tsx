import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { TopBar } from "@/components/TopBar";
import { MediaPortalDetail } from "@/components/media-portal-admin/MediaPortalDetail";
import { getPortalDetail } from "@/lib/api";

export default async function MediaPortalDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const portal = await getPortalDetail(Number(id));
  if (!portal) notFound();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <BackLink href="/media-portal" label="Média Portálok" />
        <MediaPortalDetail portal={portal} />
      </div>
    </div>
  );
}
