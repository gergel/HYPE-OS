import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { TopBar } from "@/components/TopBar";
import { formatDate, getPendingSubcontractorProjects } from "@/lib/api";

/** Alvállalkozók szerződése: projektenként összegyűjti, hogy a diszpó
 * kiküldése után kik vettek részt a projekten, akik sem nem belsősök, sem
 * nincs még keretszerződésük - nekik kell egyedi (eseti) megbízási
 * szerződést generálni és kiküldeni. Csak azok a projektek látszanak itt,
 * ahol van legalább egy ilyen, még nem kezelt (kiküldött vagy kihagyott)
 * ember (lásd routes/subcontractor_contracts.py). */
export default async function AlvallalkozoiSzerzodesekPage() {
  const pending = await getPendingSubcontractorProjects();
  const projects = pending.map((p) => ({ ...p, id: p.project_id }));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Alvállalkozók szerződése (${projects.length} projekt)`}>
          <DataTable<(typeof projects)[number]>
            rows={projects}
            emptyText="Nincs függő alvállalkozói szerződés - minden diszpózott projekten mindenki belsős, keretszerződéses, vagy már el van intézve."
            getHref={(p) => `/projektek/${p.project_id}`}
            columns={[
              { header: "Projekt", render: (p) => p.project_nev ?? `#${p.project_id}`, sortAccessor: (p) => p.project_nev },
              {
                header: "Forgatás dátuma",
                render: (p) => formatDate(p.forgatas_datuma),
                sortAccessor: (p) => p.forgatas_datuma,
              },
              {
                header: "Függő emberek",
                align: "right",
                render: (p) => p.pending_count,
                sortAccessor: (p) => p.pending_count,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
