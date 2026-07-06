import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { CompleteStocktakeButton } from "@/components/stocktake/CompleteStocktakeButton";
import { StocktakeItemRow } from "@/components/stocktake/StocktakeItemRow";
import { TopBar } from "@/components/TopBar";
import { formatDate, getFieldTypes, getStocktakeSession, getStocktakeSummary } from "@/lib/api";

export default async function LeltarazasDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const sessionId = Number(id);
  const [session, summary, fieldTypes] = await Promise.all([
    getStocktakeSession(sessionId),
    getStocktakeSummary(sessionId),
    getFieldTypes("equipment"),
  ]);
  if (!session) notFound();

  const allapotOptions = fieldTypes.allapot?.options ?? [];

  const groups = new Map<string, typeof session.items>();
  for (const item of session.items) {
    const key = item.kategoria ?? "Egyéb";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/felszereles/leltarazas" label="Leltározások" />

        <Card title={`Leltározás #${session.id}`}>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3 text-[13px] text-text-secondary">
            <p>
              Indította: <span className="text-text-primary">{session.started_by_name}</span> · {formatDate(session.created_at)}
              {session.completed_at && <span className="text-text-success"> · Lezárva: {formatDate(session.completed_at)}</span>}
            </p>
            {!session.completed_at && <CompleteStocktakeButton sessionId={session.id} />}
          </div>
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
          {summary && (summary.problemas_statuszok.length > 0 || summary.hianyzo_keszletek.length > 0) ? (
            <div className="space-y-4">
              {summary.problemas_statuszok.length > 0 && (
                <div>
                  <p className="mb-1.5 text-[12px] font-medium uppercase tracking-wide text-text-muted">Ami nem "Jó" állapotú</p>
                  <div className="space-y-2">
                    {summary.problemas_statuszok.map((g) => (
                      <div key={g.status}>
                        <p className="text-[13px] font-medium text-text-primary">{g.status}</p>
                        <ul className="ml-3 text-[13px] text-text-secondary">
                          {g.items.map((i) => (
                            <li key={i.equipment_id}>
                              <a href={`/felszereles/${i.equipment_id}`} className="hover:underline">
                                {i.nev}
                              </a>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {summary.hianyzo_keszletek.length > 0 && (
                <div>
                  <p className="mb-1.5 text-[12px] font-medium uppercase tracking-wide text-text-muted">Hiányzó készlet</p>
                  <ul className="space-y-1 text-[13px] text-text-secondary">
                    {summary.hianyzo_keszletek.map((m) => (
                      <li key={m.equipment_id} className="flex items-center justify-between">
                        <a href={`/felszereles/${m.equipment_id}`} className="hover:underline">
                          {m.nev}
                        </a>
                        <span>
                          {m.counted_qty} / {m.expected_qty} db <span className="text-text-danger">(hiány: {m.hiany})</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <p className="text-[13px] text-text-muted">Egyelőre nincs eltérés vagy hiány rögzítve.</p>
          )}
        </Card>
      </div>
    </div>
  );
}
