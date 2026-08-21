import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { PerformanceCertificateManager } from "@/components/PerformanceCertificateManager";
import { SubcontractorContractManager } from "@/components/SubcontractorContractManager";
import { ElkeszultSzerzodesek } from "@/components/ElkeszultSzerzodesek";
import { SzamlazoFelSzerkeszto } from "@/components/SzamlazoFelSzerkeszto";
import { TigInvoiceManager } from "@/components/TigInvoiceManager";
import { TigSzerzodesreVarok } from "@/components/TigSzerzodesreVarok";
import { TopBar } from "@/components/TopBar";
import {
  formatDate,
  getAllContractsForProject,
  getAllTigForProject,
  getEmployees,
  getPendingSubcontractorsForProject,
  getMyPagePermissions,
  getPendingTigForProject,
  getProjektSzamlazok,
  getUtokovetesDetail,
  getVallalkozasok,
} from "@/lib/api";

/** Az Utókövetés részletnézete NEM csak egy állapot-áttekintés: EZ a papírozás
 * helye. Itt készül a szerződés és a TIG, itt dől el, ki számláz kiért, és itt
 * látszik a kifizetés.
 *
 * A Projekt oldalon a papírozás MŰVELETEI szándékosan nincsenek meg: az az
 * oldal a diszponálásé (forgatás, stáb, technika, diszpó), a papírozás pedig
 * hetekkel később, más kézben és egyszerre több projektre történik - két
 * helyen ugyanaz csak azt érte el, hogy a diszpót író ember is beleakadt. Az
 * ÁLLÁSUK viszont ott is látszik, áttekintésként, innen ki nem vett adatból
 * (lásd components/projekt/ProjektPapirokEsKoltsegek.tsx), és onnan ide vezet
 * a link. A DISZPÓ felől megnyitott projekten az a blokk sem jelenik meg.
 *
 * A Belsős TIG itt nem jelenik meg - az havi, nem projektenkénti,
 * lásd /belsos-tig. */
export default async function UtokovetesDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectId = Number(id);
  const [
    detail,
    pendingContracts,
    osszesSzerzodes,
    pendingTig,
    allTig,
    allEmployees,
    pagePermissions,
    szamlazoNezet,
    cegek,
  ] = await Promise.all([
    getUtokovetesDetail(projectId),
    getPendingSubcontractorsForProject(projectId),
    getAllContractsForProject(projectId),
    getPendingTigForProject(projectId),
    getAllTigForProject(projectId),
    getEmployees(),
    getMyPagePermissions(),
    getProjektSzamlazok(projectId),
    getVallalkozasok(),
  ]);
  if (!detail) notFound();

  // Aki az oldalon szerkeszthet, az a TIG állapotát is kézzel át tudja állítani.
  const canEdit = pagePermissions === null || !!pagePermissions["/utokovetes"]?.includes("edit");
  // A szerződés/TIG TÖRLÉSE külön jog (a backend is azt kéri) - ez dobja
  // vissza az embert a teendők közé, hogy újat lehessen készíteni neki.
  const canDelete = pagePermissions === null || !!pagePermissions["/utokovetes"]?.includes("delete");

  const employeeNameById = new Map(allEmployees.map((e) => [e.id, e.full_name]));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-8">
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

        {/* Ez az első kérdés a papírozásban: kinek a nevére megy a szerződés
            és a TIG (lásd SzamlazoFelSzerkeszto). */}
        <Card title="Ki számláz kiért">
          {szamlazoNezet ? (
            <SzamlazoFelSzerkeszto
              nezet={szamlazoNezet}
              cegek={cegek.filter((c) => c.aktiv).map((c) => ({ id: c.id, nev: c.nev }))}
              canEdit={canEdit}
            />
          ) : (
            <p className="text-[13px] text-text-secondary">A számlázási beállítás most nem érhető el.</p>
          )}
        </Card>

        <Card title="Szerződés készítés">
          <SubcontractorContractManager projectId={projectId} pending={pendingContracts?.pending ?? []} />
          {/* A kiküldött szerződés eltűnik a fenti (teendő-)listáról - itt
              látszik, kinek van kész papírja, és hol van. */}
          <ElkeszultSzerzodesek
            projectId={projectId}
            szerzodesek={osszesSzerzodes}
            canEdit={canEdit}
            canDelete={canDelete}
          />
        </Card>

        <Card title="Teljesítési igazolás (Külsős TIG)">
          {pendingTig?.tig_ready ? (
            <PerformanceCertificateManager
              projectId={projectId}
              pending={pendingTig.pending}
              teljesitesAlap={pendingTig.teljesites_szoveg_alap}
            />
          ) : (
            <p className="text-[13px] text-text-secondary">
              Teljesítési igazolás félenként készíthető: amint valakinek megvan a szerződése (vagy keretszerződés
              fedi), róla azonnal mehet a TIG. Itt még senkinél nincs meg - lásd a fenti &quot;Szerződés
              készítés&quot; kártyát.
            </p>
          )}
          {/* A KIHAGYÁS nem várja meg a szerződést: kimondani, hogy innen nem
              lesz TIG, a szerződéstől függetlenül lehet (lásd
              TigSzerzodesreVarok és a backend skip_tig). */}
          <TigSzerzodesreVarok
            projectId={projectId}
            felek={pendingTig?.szerzodesre_varo ?? []}
            canEdit={canEdit}
          />
          {detail.teljesitesi_igazolasok.length > 0 && (
            <div className="mt-4 border-t border-border pt-3">
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-text-muted">
                Kifizetés (külsős + keretszerződéses; belsős nem számít)
              </p>
              <ul className="space-y-1">
                {detail.teljesitesi_igazolasok.map((t) => (
                  <li key={t.szamlazo} className="flex items-center justify-between gap-3 text-[13px]">
                    {/* A címke a lefedett embereket is megnevezi, ha a fél
                        más(ok) munkáját is számlázza. */}
                    <span className="truncate text-text-primary">{t.cimke}</span>
                    {t.szamla_kihagyva ? (
                      // Szándékosan nincs számla és kifizetés - nem hiány, és
                      // az utókövetésben sem marad függőben.
                      <StatusBadge label="Számla kihagyva" tone="neutral" />
                    ) : t.szamla_kifizetve ? (
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
            // A projekt ÖSSZES számlázó fele: akinek nincs kész TIG-je, annál
            // is elvégezhető a számla-lépés kihagyása - a három lépés kihagyása
            // független egymástól.
            szamlaraVarok={detail.teljesitesi_igazolasok.map((t) => ({ szamlazo: t.szamlazo, nev: t.cimke }))}
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
