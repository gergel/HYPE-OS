import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import { KoltsegBontas } from "@/components/KoltsegBontas";
import { MegrendeloiPapirKezelo } from "@/components/megrendeloi/MegrendeloiPapirKezelo";
import { PapirKapcsolok } from "@/components/megrendeloi/PapirKapcsolok";
import { ProjektkodBontasTablak } from "@/components/projektkod/ProjektkodBontasTablak";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  formatHuf,
  getAttachments,
  getCurrentUser,
  getMegrendeloiKeretek,
  getMegrendeloiKontaktok,
  getMegrendeloiPapirok,
  getMyPagePermissions,
  getProjektkodBontas,
  getRecord,
  getRelated,
} from "@/lib/api";
import { canDoAction } from "@/lib/permissions";
import { FileCheck2, FileSignature, Receipt, TrendingDown, TrendingUp, Wallet } from "lucide-react";

const PAGE = "/projektek/project-kodok";

/** A rekord mezői nyers JSON-ból jönnek, ezért a számokat ellenőrizni kell -
 * hiányzó mező vagy régi válasz esetén nullát adunk vissza, nem NaN-t. */
function szam(ertek: unknown): number {
  return typeof ertek === "number" ? ertek : 0;
}

function szoveg(ertek: unknown): string | null {
  return typeof ertek === "string" && ertek.trim() ? ertek : null;
}

export default async function ProjectCodeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectCodeId = Number(id);
  const projectCode = await getRecord(ENTITY_PATHS.projectCode, projectCodeId);
  if (!projectCode) notFound();

  const [
    revenues,
    megrendeloiSzerzodesek,
    megrendeloiTigek,
    megrendeloiKeretek,
    megrendeloiKontaktok,
    bontas,
    pagePermissions,
    currentUser,
    attachments,
  ] = await Promise.all([
    getRelated(ENTITY_PATHS.revenue, { project_code_id: projectCodeId }),
    // A megrendelői papírok (lásd backend routes/megrendeloi_papirok.py): a
    // szerződő fél a keretszerződésekből vagy a megrendelői kontaktokból
    // választható, ezért mindkét lista kell a szerkesztőhöz.
    getMegrendeloiPapirok("szerzodes", projectCodeId),
    getMegrendeloiPapirok("tig", projectCodeId),
    getMegrendeloiKeretek(),
    getMegrendeloiKontaktok(),
    // A tételes költségbontás EGY hívásban - a korábbi oldal négy külön
    // kapcsolt-listát töltött be, és egyiken sem látszott, mi mennyibe került.
    getProjektkodBontas(projectCodeId),
    getMyPagePermissions(),
    getCurrentUser(),
    getAttachments("projectCode", projectCodeId),
  ]);

  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");

  // A papírozás állását a SZERVER mondja meg (lásd backend
  // models/project_code.py): mit számít lezártnak, és hogy kell-e egyáltalán
  // eseti szerződés (élő keretszerződés alatt nem). Ha ezt itt újraszámolnám,
  // a lista és az adatlap előbb-utóbb mást mondana.
  const kellPapir = projectCode.papir_kell !== false;
  const szerzodesKesz = projectCode.szerzodes_kell === false || projectCode.szerzodes_kesz === true;
  const tigKesz = projectCode.tig_kesz === true;
  // A SZÁMLA a papírozás harmadik lépése: akkor kerül sorra, ha a szerződés és
  // a TIG is megvan - ugyanaz a sorrend, mint az alvállalkozói oldalon.
  const szamlazhat = !kellPapir || (szerzodesKesz && tigKesz);
  const szamlak = attachments.filter((a) => a.kategoria === "szamla");

  const bevetel = revenues.reduce((sum, r) => sum + (typeof r.brutto === "number" ? r.brutto : 0), 0);
  const profit = szam(projectCode.becsult_profit);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-8">
        {/* FEJLÉC: a kód, a projekt neve és a dátuma - ennyi azonosítja a
            munkát. Minden más (ügyfél, státusz-mezők, Notion-maradékok) a
            listán és a Pénzügyekben ott van, ide csak zajt hozna. */}
        <div className="space-y-2">
          <BackLink href="/projektek/project-kodok" label="Project Code-ok" />
          <h1 className="t-page">{String(projectCode.projektkod ?? `Project Code #${projectCode.id}`)}</h1>
          <p className="text-[15px] text-text-primary">{szoveg(projectCode.project_nev) ?? "Nincs megadva projekt név"}</p>
          {szoveg(projectCode.datum_megjegyzes) && (
            <p className="text-[13px] text-text-secondary">{szoveg(projectCode.datum_megjegyzes)}</p>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard label="Bevétel" value={formatHuf(bevetel)} icon={TrendingUp} tone="teal" />
          <StatCard
            label="Összes költség"
            value={formatHuf(szam(projectCode.osszes_koltseg))}
            icon={TrendingDown}
            tone="orange"
          />
          <StatCard
            label="Becsült profit"
            value={formatHuf(profit)}
            icon={Wallet}
            tone={profit >= 0 ? "accent" : "danger"}
          />
        </div>

        {/* MIBŐL áll a költség: a négy rész összege pontosan a fenti "Összes
            költség". A belsős napidíjnak nincs Kiadás sora (a havi alapbér a
            hónap végén, egyben megy be), ezért azt külön meg is jegyezzük. */}
        <KoltsegBontas
          kulsos={szam(projectCode.kulsos_koltseg)}
          egyeb={szam(projectCode.egyeb_kiadas)}
          vagas={szam(projectCode.vagas_koltseg)}
          belsos={szam(projectCode.belsos_munka_koltseg)}
          osszesen={szam(projectCode.osszes_koltseg)}
        />

        {/* MEGRENDELŐI PAPÍROZÁS, három lépésben: szerződés → TIG → számla.
            Ugyanaz a sorrend, mint az alvállalkozói oldalon, és ugyanúgy a
            sorrend maga az információ: a számla addig nem nyílik meg, amíg az
            első kettő nincs meg - így ránézésre látszik, hol tart a munka. */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <Card title="1. Megrendelői szerződés" icon={FileSignature}>
            <MegrendeloiPapirKezelo
              projectCodeId={projectCodeId}
              fajta="szerzodes"
              papirok={megrendeloiSzerzodesek}
              keretek={megrendeloiKeretek}
              kontaktok={megrendeloiKontaktok}
              canEdit={canEdit}
              canDelete={canDelete}
              kellPapir={kellPapir}
            />
          </Card>
          <Card title="2. Megrendelői TIG" icon={FileCheck2}>
            <MegrendeloiPapirKezelo
              projectCodeId={projectCodeId}
              fajta="tig"
              papirok={megrendeloiTigek}
              keretek={megrendeloiKeretek}
              kontaktok={megrendeloiKontaktok}
              canEdit={canEdit}
              canDelete={canDelete}
              kellPapir={kellPapir}
            />
          </Card>
          <Card title="3. Számla" icon={Receipt}>
            {szamlazhat ? (
              <DokumentumFeltoltes
                entityType="projectCode"
                entityId={projectCodeId}
                attachments={szamlak}
                kategoria="szamla"
                canEdit={canEdit}
                canDelete={canDelete}
                emptyText="Nincs feltöltött számla."
              />
            ) : (
              // Nem tiltás, hanem sorrend: a számla a papírok után jön. Ha
              // valamiért mégis kell, a hiányzó papírt kell rendezni (vagy
              // kihagyni) - így a lépés nem marad nyom nélkül.
              <div className="space-y-2">
                <p className="text-[13px] text-text-secondary">
                  Előbb a szerződés és a TIG - a számla utánuk jön.
                </p>
                <div className="flex flex-wrap gap-2">
                  <StatusBadge
                    label={szerzodesKesz ? "Szerződés megvan" : "Szerződés hiányzik"}
                    tone={szerzodesKesz ? "success" : "warning"}
                  />
                  <StatusBadge label={tigKesz ? "TIG megvan" : "TIG hiányzik"} tone={tigKesz ? "success" : "warning"} />
                </div>
                {szamlak.length > 0 && (
                  // Ha korábbról MÁR van feltöltött számla, azt nem rejtjük el:
                  // a papír-sorrend nem teheti láthatatlanná a meglévő adatot.
                  <div className="border-t border-border pt-2">
                    <DokumentumFeltoltes
                      entityType="projectCode"
                      entityId={projectCodeId}
                      attachments={szamlak}
                      kategoria="szamla"
                      canEdit={false}
                      canDelete={canDelete}
                    />
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>

        {/* Kell-e egyáltalán papír erre a kódra. Nem kapott saját kártyát: a
            legtöbb munkánál nincs vele dolgunk, csak a kivételeknél (nem
            szerződéses munka, vagy máshol elszámolt) - de valahonnan
            állíthatónak kell lennie, különben az ilyen kódok örökre a
            teendők közt maradnának. */}
        {canEdit && (
          <details className="rounded-[var(--radius-lg)] border border-border px-4 py-3">
            <summary className="cursor-pointer text-[12.5px] text-text-muted hover:text-text-secondary">
              Nem kell ide papír? (nem szerződéses munka, vagy máshol elszámolt)
            </summary>
            <div className="mt-3">
              <PapirKapcsolok
                patchPath={`${ENTITY_PATHS.projectCode}/${projectCodeId}`}
                vanSzerzodes={projectCode.van_szerzodes !== false}
                papirNelkul={projectCode.papir_nelkul === true}
                papirNelkulIndoka={szoveg(projectCode.papir_nelkul_indoka)}
                canEdit={canEdit}
              />
            </div>
          </details>
        )}

        {/* A TÉTELES bontás: melyik forgatás mennyibe került, melyik anyagot
            meddig vágtuk, és milyen kiadások terhelik a kódot. */}
        {bontas ? (
          <ProjektkodBontasTablak bontas={bontas} />
        ) : (
          <Card title="Költségek tételesen">
            <p className="text-[13px] text-text-secondary">A bontás most nem érhető el.</p>
          </Card>
        )}
      </div>
    </div>
  );
}
