import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getFieldTypes, getRecord, getVisibleFields } from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";

export default async function RevenueDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const revenueId = Number(id);
  const revenue = await getRecord(ENTITY_PATHS.revenue, revenueId);
  if (!revenue) notFound();

  const [projectCode, visibleFields, fieldTypes] = await Promise.all([
    revenue.project_code_id ? getRecord(ENTITY_PATHS.projectCode, Number(revenue.project_code_id)) : null,
    getVisibleFields("revenue"),
    getFieldTypes("revenue"),
  ]);
  // Honnan jött a bevétel: a projektkód mögötti ügyfél.
  const ugyfel = projectCode?.client_id
    ? await getRecord(ENTITY_PATHS.client, Number(projectCode.client_id))
    : null;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <BackLink href="/penzugyek" label="Pénzügyek" />

        <Card title={String(revenue.bevetel_formaja ?? `Bevétel #${revenue.id}`)}>
          <div className="mb-4 flex flex-wrap gap-4 text-[13px] text-text-secondary">
            {ugyfel && (
              <a href={`/ugyfelek/${ugyfel.id}`} className="text-text-accent hover:underline">
                Ügyfél: {String(ugyfel.nev)}
              </a>
            )}
            {projectCode && (
              <a href={`/projektek/project-kodok/${projectCode.id}`} className="text-text-accent hover:underline">
                Project Code: {String(projectCode.projektkod)}
              </a>
            )}
          </div>
          <EditableDetailGrid
            patchPath={`${ENTITY_PATHS.revenue}/${revenue.id}`}
            fields={toEditableDetailFields(revenue, ["project_code_id"], visibleFields, fieldTypes)}
          />
        </Card>
      </div>
    </div>
  );
}
