import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { StartStocktakeButton } from "@/components/stocktake/StartStocktakeButton";
import { TopBar } from "@/components/TopBar";
import { getStocktakeSessions, formatDate } from "@/lib/api";

export default async function LeltarazasListPage() {
  const sessions = await getStocktakeSessions();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-8">
        <BackLink href="/felszereles" label="Felszerelés" />

        <Card title="Leltározás">
          <p className="mb-3 text-[13px] text-text-secondary">
            Egy leltározás minden felvett eszközt felsorol - végig lehet menni rajtuk, jelölve hogy megvan-e / szerelni kell-e, a
            készlet-alapú eszközöknél pedig megadható a ténylegesen megszámolt darabszám. A végén itt látszik, mi romlott el és
            miből mennyi hiányzik.
          </p>
          <StartStocktakeButton />
        </Card>

        <Card title={`Korábbi leltározások (${sessions.length})`}>
          {sessions.length === 0 && <p className="text-[13px] text-text-muted">Még nem volt leltározás.</p>}
          <div className="divide-y divide-border">
            {sessions.map((s) => (
              <a
                key={s.id}
                href={`/felszereles/leltarazas/${s.id}${s.completed_at ? "/eredmeny" : ""}`}
                className="flex items-center justify-between gap-3 py-2.5 text-[13px] hover:bg-surface-3"
              >
                <div>
                  <p className="text-text-primary">
                    #{s.id} - {s.started_by_name}
                  </p>
                  <p className="text-[12px] text-text-muted">{formatDate(s.created_at)}</p>
                </div>
                <span className={s.completed_at ? "text-text-success" : "text-text-warning"}>
                  {s.completed_at ? "Lezárva" : "Folyamatban"}
                </span>
              </a>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
