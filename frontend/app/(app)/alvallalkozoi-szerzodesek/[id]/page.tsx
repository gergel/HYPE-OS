import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { SubcontractorContractRow } from "@/components/SubcontractorContractRow";
import { formatDate, getPendingSubcontractorsForProject } from "@/lib/api";

export default async function AlvallalkozoiSzerzodesProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const detail = await getPendingSubcontractorsForProject(Number(id));
  if (!detail) notFound();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/alvallalkozoi-szerzodesek" label="Alvállalkozók szerződése" />
        <Card title={detail.project_nev ?? `Projekt #${detail.project_id}`}>
          <p className="mb-4 text-[13px] text-text-muted">Forgatás dátuma: {formatDate(detail.forgatas_datuma)}</p>
          <div className="space-y-3">
            {detail.pending.length === 0 && (
              <p className="text-[13px] text-text-muted">
                Nincs több függő ember ezen a projekten - mindenki kiküldve vagy kihagyva.
              </p>
            )}
            {detail.pending.map((employee) => (
              <SubcontractorContractRow key={employee.id} projectId={detail.project_id} employee={employee} />
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
