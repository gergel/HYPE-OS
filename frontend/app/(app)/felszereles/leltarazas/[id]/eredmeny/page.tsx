import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DeleteStocktakeButton } from "@/components/stocktake/DeleteStocktakeButton";
import { LeltarOsszesites } from "@/components/stocktake/LeltarOsszesites";
import { TopBar } from "@/components/TopBar";
import { formatDate, getCurrentUser, getStocktakeSession, getStocktakeSummary } from "@/lib/api";
import { szerepkorei } from "@/lib/permissions";

export default async function LeltarazasEredmenyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const sessionId = Number(id);
  const [session, summary, currentUser] = await Promise.all([
    getStocktakeSession(sessionId),
    getStocktakeSummary(sessionId),
    getCurrentUser(),
  ]);
  if (!session || !summary) notFound();

  // A törlés admin-jog (a backend is azt kéri, lásd routes/stocktake.py).
  const admin = szerepkorei(currentUser).includes("admin");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-8">
        <BackLink href="/felszereles/leltarazas" label="Leltározások" />

        <Card title={`Leltározás #${session.id} eredménye`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[13px] text-text-secondary">
              Indította: <span className="text-text-primary">{session.started_by_name}</span> · {formatDate(session.created_at)}
              {session.completed_at && <span className="text-text-success"> · Lezárva: {formatDate(session.completed_at)}</span>}
            </p>
            {admin && <DeleteStocktakeButton sessionId={session.id} />}
          </div>
        </Card>

        <Card title="Amit érdemes intézni">
          <LeltarOsszesites
            summary={summary}
            ures={'Minden eszköz "Jó" állapotú, és minden készlet pontosan annyi, amennyinek lennie kell - nincs teendő.'}
          />
        </Card>
      </div>
    </div>
  );
}
