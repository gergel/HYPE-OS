import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { PerformanceCertificateManager } from "@/components/PerformanceCertificateManager";
import { SubcontractorContractManager } from "@/components/SubcontractorContractManager";
import { TigInvoiceManager } from "@/components/TigInvoiceManager";
import { TopBar } from "@/components/TopBar";
import {
  formatDate,
  getAllTigForProject,
  getEmployees,
  getPendingSubcontractorsForProject,
  getMyPagePermissions,
  getPendingTigForProject,
  getUtokovetesDetail,
} from "@/lib/api";

/** Az Utókövetés részletnézete NEM csak egy állapot-áttekintés, hanem itt is
 * el lehet készíteni a szerződéseket és a TIG-eket - ugyanazok a
 * (SubcontractorContractManager/PerformanceCertificateManager/
 * TigInvoiceManager) komponensek, amik a Projekt oldal "Szerződés & TIG"
 * szekciójában is szerepelnek -, hogy ne kelljen admin a Projekt oldalra
 * átnavigálnia csak azért, hogy egy hátralévő tételt lezárjon. A Belsős TIG
 * itt nem jelenik meg - az havi, nem projektenkénti, lásd /belsos-tig. */
export default async function UtokovetesDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectId = Number(id);
  const [detail, pendingContracts, pendingTig, allTig, allEmployees, pagePermissions] = await Promise.all([
    getUtokovetesDetail(projectId),
    getPendingSubcontractorsForProject(projectId),
    getPendingTigForProject(projectId),
    getAllTigForProject(projectId),
    getEmployees(),
    getMyPagePermissions(),
  ]);
  if (!detail) notFound();

  // Aki az oldalon szerkeszthet, az a TIG állapotát is kézzel át tudja állítani.
  const canEdit = pagePermissions === null || !!pagePermissions["/utokovetes"]?.includes("edit");

  const employeeNameById = new Map(allEmployees.map((e) => [e.id, e.full_name]));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-6">
        <BackLink href="/utokovetes" label="Utókövetés" />

        <Card title={detail.project_nev ?? `Projekt #${detail.project_id}`}>
          {/* A projekt csak akkor teljesen kész, ha az alvállalkozók ki is
              vannak fizetve - nem elég a szerződés + TIG (lásd backend
              utokovetes_admin.py _kifizetes_state). */}
          <div className="mb-3 flex flex-wrap items-center gap-3">
            {detail.kesz ? (
              <StatusBadge label="Teljesen kész" tone="success" />
            ) : (
              <StatusBadge label="Folyamatban" tone="warning" />
            )}
            <span className="text-[13px] text-text-secondary">
              {detail.kifizetes_osszes === 0
                ? "Nincs kifizetendő alvállalkozó ezen a projekten."
                : detail.kifizetes_fuggo === 0
                  ? `Mind a(z) ${detail.kifizetes_osszes} alvállalkozó ki van fizetve.`
                  : `${detail.kifizetes_fuggo} / ${detail.kifizetes_osszes} alvállalkozó még nincs kifizetve.`}
            </span>
          </div>
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

        <Card title="Szerződés készítés">
          <SubcontractorContractManager projectId={projectId} pending={pendingContracts?.pending ?? []} />
        </Card>

        <Card title="Teljesítési igazolás (Külsős TIG)">
          {pendingTig?.tig_ready ? (
            <PerformanceCertificateManager projectId={projectId} pending={pendingTig.pending} />
          ) : (
            <p className="text-[13px] text-text-secondary">
              Teljesítési igazolás csak azután készíthető, hogy mindenkinek megvan a szerződés státusza (kiküldve vagy
              kihagyva) - lásd a fenti &quot;Szerződés készítés&quot; kártyát.
            </p>
          )}
          {detail.teljesitesi_igazolasok.length > 0 && (
            <div className="mt-4 border-t border-border pt-3">
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                Kifizetés (külsős + keretszerződéses; belsős nem számít)
              </p>
              <ul className="space-y-1">
                {detail.teljesitesi_igazolasok.map((t) => (
                  <li key={t.id} className="flex items-center justify-between gap-3 text-[13px]">
                    <span className="truncate text-text-primary">{t.full_name}</span>
                    {t.szamla_kifizetve ? (
                      <StatusBadge label="Kifizetve" tone="success" />
                    ) : t.van_szamla ? (
                      <StatusBadge label="Számla feltöltve, nincs kifizetve" tone="warning" />
                    ) : (
                      <StatusBadge label="Nincs számla" tone="neutral" />
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <TigInvoiceManager
            projectId={projectId}
            basePath="/api/v1/teljesitesi-igazolasok"
            certificates={allTig}
            employeeNameById={employeeNameById}
            readyStatus="Kiküldve"
            canEdit={canEdit}
          />
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
