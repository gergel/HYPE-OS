import { notFound } from "next/navigation";
import { ProjectDetailContent } from "@/components/ProjectDetailContent";
import { ENTITY_PATHS, getRecord } from "@/lib/api";

/** A Projekt részletnézet felugró ablakba szánt változata - a
 * ProjectDetailModal tölti be iframe-ben a Projektek lista/naptár és a
 * Naptár/Diszpó oldalról. Ugyanaz a tartalom és ugyanazok a műveletek, mint a
 * /projektek/[id] oldalon (lásd ProjectDetailContent), csak az alkalmazás-keret
 * nélkül. A jogosultság-ellenőrzést a middleware ugyanúgy elvégzi, mint a
 * rendes oldalnál (lásd middleware.ts - az /embed előtagot levágja). */
export default async function EmbeddedProjectDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ nezet?: string }>;
}) {
  const { id } = await params;
  const { nezet } = await searchParams;
  const projectId = Number(id);
  const project = await getRecord(ENTITY_PATHS.project, projectId);
  if (!project) notFound();

  // A DISZPÓ felől szűkített nézet nyílik (lásd ProjectDetailModal `nezet`) -
  // a Projektek listából ugyanez a projekt teljesen.
  return <ProjectDetailContent projectId={projectId} embedded csakDiszpoNezet={nezet === "diszpo"} />;
}
