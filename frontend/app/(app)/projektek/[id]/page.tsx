import { notFound } from "next/navigation";
import { ProjectDetailContent } from "@/components/ProjectDetailContent";
import { ENTITY_PATHS, getRecord } from "@/lib/api";

/** A tényleges tartalom a ProjectDetailContent komponensben van, mert
 * ugyanezt jeleníti meg a lista/naptár nézetből nyíló felugró ablak is
 * (/embed/projektek/[id] -> ProjectDetailModal) - így a két nézet nem tud
 * egymástól elcsúszni. */
export default async function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectId = Number(id);
  const project = await getRecord(ENTITY_PATHS.project, projectId);
  if (!project) notFound();

  return <ProjectDetailContent projectId={projectId} />;
}
