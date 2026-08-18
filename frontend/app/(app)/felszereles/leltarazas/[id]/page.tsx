import { notFound, redirect } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { CompleteStocktakeButton } from "@/components/stocktake/CompleteStocktakeButton";
import { DeleteStocktakeButton } from "@/components/stocktake/DeleteStocktakeButton";
import { LeltarOsszesites } from "@/components/stocktake/LeltarOsszesites";
import { StocktakeItemRow } from "@/components/stocktake/StocktakeItemRow";
import { TopBar } from "@/components/TopBar";
import { formatDate, getCurrentUser, getFieldTypes, getStocktakeSession, getStocktakeSummary } from "@/lib/api";
import { szerepkorei } from "@/lib/permissions";

export default async function LeltarazasDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const sessionId = Number(id);
  const [session, summary, fieldTypes, currentUser] = await Promise.all([
    getStocktakeSession(sessionId),
    getStocktakeSummary(sessionId),
    getFieldTypes("equipment"),
    getCurrentUser(),
  ]);
  if (!session) notFound();
  // Lezárt leltározás már nem szerkeszthető - az eredményoldal a végleges nézet.
  if (session.completed_at) redirect(`/felszereles/leltarazas/${sessionId}/eredmeny`);

  const allapotOptions = fieldTypes.allapot?.options ?? [];

  const groups = new Map<string, typeof session.items>();
  for (const item of session.items) {
    const key = item.kategoria ?? "Egyéb";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }

  const magyarazatraVar = summary?.magyarazatra_var ?? [];

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-8">
        <BackLink href="/felszereles/leltarazas" label="Leltározások" />

        <Card title={`Leltározás #${session.id}`}>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-[13px] text-text-secondary">
            <p>
              Indította: <span className="text-text-primary">{session.started_by_name}</span> · {formatDate(session.created_at)}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {/* Téves vagy duplán elindított leltár takarítása - csak admin. */}
              {szerepkorei(currentUser).includes("admin") && <DeleteStocktakeButton sessionId={session.id} />}
              <CompleteStocktakeButton sessionId={session.id} />
            </div>
          </div>
          {/* Amíg van magyarázat nélküli szerelendő/szervizes eszköz, a lezárás
              elakad - jobb ezt előre látni, mint a lezárás gombnál. */}
          {magyarazatraVar.length > 0 && (
            <p className="text-[13px] text-text-danger">
              {magyarazatraVar.length} eszköznél hiányzik a magyarázat (miért szerelendő / miért van szervizben):{" "}
              {magyarazatraVar.map((i) => i.nev).join(", ")}. A leltározás addig nem zárható le.
            </p>
          )}
        </Card>

        {Array.from(groups.entries()).map(([kategoria, items]) => (
          <Card key={kategoria} title={`${kategoria} (${items.length})`}>
            <div className="divide-y divide-border">
              {items.map((item) => (
                <StocktakeItemRow key={item.id} sessionId={session.id} item={item} allapotOptions={allapotOptions} />
              ))}
            </div>
          </Card>
        ))}

        <Card title="Összesítés">
          {summary ? (
            <LeltarOsszesites summary={summary} ures="Egyelőre nincs eltérés vagy hiány rögzítve." />
          ) : (
            <p className="text-[13px] text-text-muted">Az összesítés most nem érhető el.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
