import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { EditableDetailGrid } from "@/components/EditableDetailGrid";
import { TopBar } from "@/components/TopBar";
import { ENTITY_PATHS, getFieldTypes, getRecord, getVisibleFields } from "@/lib/api";
import { toEditableDetailFields } from "@/lib/detail";

export default async function ExpenseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const expenseId = Number(id);
  const expense = await getRecord(ENTITY_PATHS.expense, expenseId);
  if (!expense) notFound();

  const [projectCode, employee, visibleFields, fieldTypes] = await Promise.all([
    expense.project_code_id ? getRecord(ENTITY_PATHS.projectCode, Number(expense.project_code_id)) : null,
    expense.employee_id ? getRecord(ENTITY_PATHS.employee, Number(expense.employee_id)) : null,
    getVisibleFields("expense"),
    getFieldTypes("expense"),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-8">
        <BackLink href="/penzugyek" label="Pénzügyek" />

        <Card title={String(expense.megnevezes ?? `Kiadás #${expense.id}`)}>
          <div className="mb-4 flex flex-wrap gap-4 text-[13px] text-text-secondary">
            {projectCode && (
              <a href={`/projektek/project-kodok/${projectCode.id}`} className="text-text-accent hover:underline">
                Project Code: {String(projectCode.projektkod)}
              </a>
            )}
            {employee && (
              <a href={`/csapat/${employee.id}`} className="text-text-accent hover:underline">
                Crew tag: {String(employee.full_name)}
              </a>
            )}
          </div>
          <EditableDetailGrid
            patchPath={`${ENTITY_PATHS.expense}/${expense.id}`}
            fields={toEditableDetailFields(expense, ["project_code_id", "employee_id"], visibleFields, fieldTypes)}
          />
        </Card>
      </div>
    </div>
  );
}
