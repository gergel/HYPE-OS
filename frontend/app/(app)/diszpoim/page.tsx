import { FileText } from "lucide-react";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { getSajatDiszpok } from "@/lib/api";

/** DISZPÓIM - gyűjtő oldal (a felhasználó kérése): a bejelentkezett
 * munkatárs itt látja listázva, milyen diszpókat kapott és milyen
 * projekteken volt. Csak a projekt neve, a dátum és a diszpó PDF-je
 * érhető el - a diszpó/projekt semmilyen más adata nem (a sor nem is
 * kattintható át az adatlapra). Minden bejelentkezett munkatársnak jár,
 * külön jogosultság nélkül: mindenki csak a sajátját látja. */
export default async function DiszpoimPage() {
  const diszpok = await getSajatDiszpok();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <Card title={`Diszpóim (${diszpok.length})`}>
          {diszpok.length === 0 ? (
            <p className="text-[13px] text-text-muted">
              Még nem voltál egyetlen forgatás stábjában sem.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-[13.5px]">
                <thead>
                  <tr className="border-b border-border text-left text-text-secondary">
                    <th className="py-2 pr-4 font-medium">Dátum</th>
                    <th className="py-2 pr-4 font-medium">Projekt</th>
                    <th className="py-2 text-right font-medium">Diszpó</th>
                  </tr>
                </thead>
                <tbody>
                  {diszpok.map((d) => (
                    <tr key={d.project_id} className="border-b border-border/60">
                      <td className="whitespace-nowrap py-2.5 pr-4 text-text-secondary">
                        {d.forgatas_datuma ? new Date(d.forgatas_datuma).toLocaleDateString("hu-HU") : "–"}
                        {d.forgatas_vege && d.forgatas_vege !== d.forgatas_datuma
                          ? ` – ${new Date(d.forgatas_vege).toLocaleDateString("hu-HU")}`
                          : ""}
                      </td>
                      <td className="py-2.5 pr-4 text-text-primary">{d.projekt_nev ?? `Forgatás #${d.project_id}`}</td>
                      <td className="py-2.5 text-right">
                        {d.pdf_url ? (
                          <a
                            href={d.pdf_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-border px-2.5 py-1.5 text-[13px] text-text-accent hover:bg-surface-3"
                          >
                            <FileText size={14} />
                            PDF megnyitása
                          </a>
                        ) : (
                          <span className="text-[12.5px] text-text-muted">nincs PDF</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
