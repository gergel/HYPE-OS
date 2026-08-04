import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { TopBar } from "@/components/TopBar";
import { formatDate, getPendingTigProjects } from "@/lib/api";

/** Teljesítési igazolások (TIG): projektenként összegyűjti azokat a
 * diszpózott projekteket, ahol az eseti szerződés fázis már lezárult
 * (mindenkinek megvan a szerződés státusza - kiküldve vagy kihagyva, lásd
 * alvallalkozoi-szerzodesek) - ezeken kell minden nem belsős stábtagnak
 * (a keretszerződéseseknek IS) teljesítési igazolást generálni és kiküldeni,
 * vagy kihagyni. Csak azok a projektek látszanak itt, ahol van legalább egy
 * ilyen, még nem kezelt ember (lásd routes/performance_certificates.py). */
export default async function TeljesitesiIgazolasokPage() {
  const pending = await getPendingTigProjects();
  const projects = pending.map((p) => ({ ...p, id: p.project_id }));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Teljesítési igazolások (${projects.length} projekt)`}>
          <DataTable<(typeof projects)[number]>
            filterable
            rows={projects}
            emptyText="Nincs függő teljesítési igazolás - minden diszpózott projekten, ahol lezárult a szerződés fázis, mindenki el van intézve."
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
