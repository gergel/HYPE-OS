import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { ElkeszultSzerzodesek } from "@/components/ElkeszultSzerzodesek";
import { ElkeszultTigProjektkod } from "@/components/ElkeszultTigProjektkod";
import { PerformanceCertificateManagerProjektkod } from "@/components/PerformanceCertificateManagerProjektkod";
import { SubcontractorContractManagerProjektkod } from "@/components/SubcontractorContractManagerProjektkod";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getAllContractsForProjectCode,
  getAllTigForProjectCode,
  getMyPagePermissions,
  getPendingSubcontractorsForProjectCode,
  getPendingTigForProjectCode,
  getRecord,
} from "@/lib/api";

/** Az Utókövetés részletnézete egy PROJEKTKÓDON, forgatás nélkül - lásd
 * /utokovetes/[id] (a forgatáshoz kötött megfelelője, ugyanaz a szerep).
 *
 * Ez a szerződés/TIG a Project Code adatlapján KORÁBBAN itt, munkafelületként
 * jelent meg - onnan került át ide, ugyanazon okból, amiért a forgatáshoz
 * kötött papírozás sincs a Projekt oldalon: a Project Code adatlap a
 * projektről/kiadásokról szól, a papírozás pedig hetekkel később, más kézben
 * történik, gyakran egyszerre több projektkódra rálátva. A Project Code
 * adatlapon csak egy rövid, olvasásra szánt állapot-kártya és egy ide mutató
 * link maradt. */
export default async function UtokovetesProjektkodDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectCodeId = Number(id);
  const projectCode = await getRecord(ENTITY_PATHS.projectCode, projectCodeId);
  if (!projectCode) notFound();

  const [pendingSzerzodes, pendingTig, keszSzerzodesek, keszTigek, pagePermissions] = await Promise.all([
    getPendingSubcontractorsForProjectCode(projectCodeId),
    getPendingTigForProjectCode(projectCodeId),
    getAllContractsForProjectCode(projectCodeId),
    getAllTigForProjectCode(projectCodeId),
    getMyPagePermissions(),
  ]);

  // Ugyanaz a jog, mint a forgatás-alapú Utókövetés oldalon.
  const canEdit = pagePermissions === null || !!pagePermissions["/utokovetes"]?.includes("edit");
  const canDelete = pagePermissions === null || !!pagePermissions["/utokovetes"]?.includes("delete");

  const cim =
    typeof projectCode.projektkod === "string" && projectCode.projektkod
      ? projectCode.projektkod
      : `Projektkód #${projectCodeId}`;
  const projektNev = typeof projectCode.project_nev === "string" ? projectCode.project_nev : null;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        <BackLink href="/utokovetes" label="Utókövetés" />

        <Card title={cim}>
          <div className="flex flex-wrap items-center gap-4 text-[13px] text-text-secondary">
            {projektNev && <span>{projektNev}</span>}
            <a href={`/projektek/project-kodok/${projectCodeId}`} className="text-text-accent hover:underline">
              Project Code megnyitása →
            </a>
          </div>
        </Card>

        <Card title="Szerződés készítés">
          <SubcontractorContractManagerProjektkod
            projectCodeId={projectCodeId}
            pending={pendingSzerzodes?.pending ?? []}
          />
          {/* A kiküldött (vagy kihagyott) szerződés eltűnik a fenti
              teendő-listáról - itt látszik, kinek van kész papírja. */}
          <ElkeszultSzerzodesek
            projectId={projectCodeId}
            szerzodesek={keszSzerzodesek}
            canEdit={canEdit}
            canDelete={canDelete}
            basePath={`/api/v1/alvallalkozoi-szerzodesek/projektkodok/${projectCodeId}`}
          />
        </Card>

        <Card title="Teljesítési igazolás (Külsős TIG)">
          <PerformanceCertificateManagerProjektkod
            projectCodeId={projectCodeId}
            pending={pendingTig?.pending ?? []}
            szerzodesreVaro={pendingTig?.szerzodesre_varo ?? []}
          />
          <ElkeszultTigProjektkod
            projectCodeId={projectCodeId}
            tigek={keszTigek}
            canEdit={canEdit}
            canDelete={canDelete}
          />
        </Card>
      </div>
    </div>
  );
}
