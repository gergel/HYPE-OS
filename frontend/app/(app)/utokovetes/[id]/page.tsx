import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { formatDate, getUtokovetesDetail } from "@/lib/api";

function personRow(person: { id: number; full_name: string; email: string | null }, allapot: string | null | undefined) {
  const tone = allapot === "Kiküldve" ? "success" : allapot === "Kihagyva" ? "neutral" : "warning";
  const label = allapot ?? "Nincs elkezdve";
  return (
    <tr key={person.id} className="border-b border-border last:border-0">
      <td className="py-2 pr-4">
        <a href={`/csapat/${person.id}`} className="text-text-accent hover:underline">
          {person.full_name}
        </a>
      </td>
      <td className="py-2 pr-4 text-text-secondary">{person.email ?? "–"}</td>
      <td className="py-2 text-right">
        <StatusBadge label={label} tone={tone} />
      </td>
    </tr>
  );
}

export default async function UtokovetesDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectId = Number(id);
  const detail = await getUtokovetesDetail(projectId);
  if (!detail) notFound();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/utokovetes" label="Utókövetés" />

        <Card title={detail.project_nev ?? `Projekt #${detail.project_id}`}>
          <div className="flex flex-wrap gap-4 text-[13px] text-text-secondary">
            {detail.projektkod && <span>Projektkód: {detail.projektkod}</span>}
            <span>
              Forgatás: {formatDate(detail.forgatas_datuma)}
              {detail.forgatas_datuma_vege && detail.forgatas_datuma_vege !== detail.forgatas_datuma
                ? ` – ${formatDate(detail.forgatas_datuma_vege)}`
                : ""}
            </span>
            <a href={`/projektek/${detail.project_id}`} className="text-text-accent hover:underline">
              Projekt megnyitása →
            </a>
          </div>
        </Card>

        <Card title={`Szerződések (${detail.szerzodesek.length})`}>
          {detail.szerzodesek.length === 0 ? (
            <p className="text-[13px] text-text-secondary">Nincs olyan résztvevő, akinek eseti szerződést kellene készíteni.</p>
          ) : (
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-1.5 text-left font-medium text-text-secondary">Név</th>
                  <th className="py-1.5 text-left font-medium text-text-secondary">Email</th>
                  <th className="py-1.5 text-right font-medium text-text-secondary">Állapot</th>
                </tr>
              </thead>
              <tbody>{detail.szerzodesek.map((s) => personRow(s, s.draft?.szerzodes_allapota))}</tbody>
            </table>
          )}
        </Card>

        <Card title={`Teljesítési igazolások (${detail.teljesitesi_igazolasok.length})`}>
          {!detail.tig_ready ? (
            <p className="text-[13px] text-text-secondary">
              Teljesítési igazolás csak azután készíthető, hogy mindenkinek megvan a szerződés státusza (kiküldve vagy kihagyva).
            </p>
          ) : detail.teljesitesi_igazolasok.length === 0 ? (
            <p className="text-[13px] text-text-secondary">Nincs olyan résztvevő, akinek teljesítési igazolást kellene készíteni.</p>
          ) : (
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-1.5 text-left font-medium text-text-secondary">Név</th>
                  <th className="py-1.5 text-left font-medium text-text-secondary">Email</th>
                  <th className="py-1.5 text-right font-medium text-text-secondary">Állapot</th>
                </tr>
              </thead>
              <tbody>{detail.teljesitesi_igazolasok.map((t) => personRow(t, t.draft?.allapot))}</tbody>
            </table>
          )}
        </Card>

        <Card title={`Visszajelzések (${detail.visszajelzesek.length})`}>
          {detail.visszajelzesek.length === 0 ? (
            <p className="text-[13px] text-text-secondary">Még nem érkezett kitöltött kérdőív erre a projektre.</p>
          ) : (
            <div className="space-y-4">
              {detail.visszajelzesek.map((f) => (
                <div key={f.id} className="rounded-[var(--radius)] border border-border p-4">
                  <p className="mb-3 text-[11px] text-text-muted">
                    {new Date(f.created_at).toLocaleString("hu-HU", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                  <div className="space-y-3 text-[13px]">
                    <div>
                      <p className="text-[11px] text-text-muted">Történt-e érdemleges esemény a forgatáson?</p>
                      <p className="text-text-primary">{f.erdemleges_tortent || "–"}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-text-muted">Technikai információ</p>
                      <p className="text-text-primary">{f.technika_info || "–"}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-text-muted">Egyéb</p>
                      <p className="text-text-primary">{f.egyeb || "–"}</p>
                    </div>
                    {f.werk_fotok && f.werk_fotok.length > 0 && (
                      <div>
                        <p className="mb-1 text-[11px] text-text-muted">Werk fotók ({f.werk_fotok.length})</p>
                        <div className="flex flex-wrap gap-2">
                          {f.werk_fotok.map((photo, idx) => (
                            <a
                              key={idx}
                              href={photo.url}
                              target="_blank"
                              rel="noreferrer"
                              className="rounded-[var(--radius)] border border-border px-2 py-1 text-text-accent hover:underline"
                            >
                              {photo.filename}
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
