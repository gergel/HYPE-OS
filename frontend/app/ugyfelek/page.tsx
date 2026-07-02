import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { TopBar } from "@/components/TopBar";
import { Client, getClients } from "@/lib/api";

export default async function UgyfelekPage() {
  const clients = await getClients();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Ügyfelek (${clients.length})`}>
          <DataTable<Client>
            rows={clients}
            emptyText="Még nincs felvett ügyfél - importáld a Notionból, vagy adj hozzá egyet a /api/v1/clients végponton."
            columns={[
              { header: "Név", render: (c) => c.nev },
              { header: "Adószám", render: (c) => c.adoszam ?? "–" },
              { header: "Székhely", render: (c) => c.szekhely ?? "–" },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
