import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { Equipment, getEquipment } from "@/lib/api";

export default async function FelszerelesPage() {
  const equipment = await getEquipment();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-6">
        <Card title={`Felszerelés (${equipment.length})`}>
          <DataTable<Equipment>
            rows={equipment}
            emptyText="Még nincs felvett eszköz - importáld a Notionból, vagy adj hozzá egyet a /api/v1/equipment végponton."
            columns={[
              { header: "Név", render: (e) => e.nev },
              { header: "Kategória", render: (e) => e.kategoria ?? "–" },
              { header: "Állapot", render: (e) => e.allapot ?? "–" },
              {
                header: "Track mode",
                render: (e) => <StatusBadge label={e.track_mode === "stock" ? "Készlet" : "Egyedi"} tone="neutral" />,
              },
              { header: "Mennyiség", align: "right", render: (e) => e.osszes_mennyiseg ?? "–" },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
