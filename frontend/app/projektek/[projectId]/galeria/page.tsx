import { Card } from "@/components/Card";
import { GalleryExportPanel } from "@/components/GalleryExportPanel";
import { TopBar } from "@/components/TopBar";

export default async function ProjectGalleryPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const id = Number.parseInt(projectId, 10);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex flex-1 flex-col gap-4 p-6">
        <Card title={`Galéria · Projekt #${Number.isNaN(id) ? "?" : id}`}>
          {Number.isNaN(id) ? (
            <p className="text-[13px] text-text-danger">Érvénytelen projekt-azonosító.</p>
          ) : (
            <GalleryExportPanel projectId={id} />
          )}
        </Card>
      </div>
    </div>
  );
}
