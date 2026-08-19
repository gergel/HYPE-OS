import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import { KoltsegBontas } from "@/components/KoltsegBontas";
import { KeretKotes } from "@/components/megrendeloi/KeretKotes";
import { MegrendeloiPapirKezelo } from "@/components/megrendeloi/MegrendeloiPapirKezelo";
import { MegrendeloiSzamla } from "@/components/megrendeloi/MegrendeloiSzamla";
import { PapirKapcsolok } from "@/components/megrendeloi/PapirKapcsolok";
import { ProjektkodBontasTablak } from "@/components/projektkod/ProjektkodBontasTablak";
import { VallalasiAr } from "@/components/projektkod/VallalasiAr";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  formatHuf,
  getAttachments,
  getClients,
  getCurrentUser,
  getMegrendeloiKeretek,
  getMegrendeloiKontaktok,
  getMegrendeloiPapirok,
  getMegrendeloiSzamlaAllas,
  getMyPagePermissions,
  getProjektkodBontas,
  getRecord,
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
    megrendeloiSzerzodesek,
    megrendeloiTigek,
    megrendeloiKeretek,
    megrendeloiKontaktok,
    clients,
    bontas,
    pagePermissions,
    currentUser,
    attachments,
    szamlaAllas,
  ] = await Promise.all([
    // A megrendelői papírok (lásd backend routes/megrendeloi_papirok.py): a
    // szerződő fél a MEGRENDELŐK közül választható, a kapcsolattartó pedig a
    // megrendelői kontaktokból - ezért kell mindkét lista a szerkesztőhöz.
    // A keretszerződések listája a keret-kötéshez kell (KeretKotes).
    getMegrendeloiPapirok("szerzodes", projectCodeId),
    getMegrendeloiPapirok("tig", projectCodeId),
    getMegrendeloiKeretek(),
    getMegrendeloiKontaktok(),
    // A MEGRENDELŐK: a papír szerződő fele közülük kerül ki (a
    // keretszerződés-lista erre rossz kérdés volt - lásd
    // MegrendeloiPapirKezelo).
    getClients(),
    // A tételes költségbontás EGY hívásban - a korábbi oldal négy külön
    // kapcsolt-listát töltött be, és egyiken sem látszott, mi mennyibe került.
    getProjektkodBontas(projectCodeId),
    getMyPagePermissions(),
    getCurrentUser(),
    getAttachments("projectCode", projectCodeId),
    // A számla-lépés állása: határidő, kifizetés napja, és hogy keletkezett-e
    // bevétel-sor (lásd backend services/megrendeloi_szamla.py).
    getMegrendeloiSzamlaAllas(projectCodeId),
  ]);

  const ugyfelek = clients
    .map((c) => ({ id: c.id, nev: c.nev }))
    .sort((a, b) => a.nev.localeCompare(b.nev, "hu"));

  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");

  // A papírozás állását a SZERVER mondja meg (lásd backend
  // models/project_code.py): mit számít lezártnak, és hogy kell-e egyáltalán
  // eseti szerződés (élő keretszerződés alatt nem). Ha ezt itt újraszámolnám,
  // a lista és az adatlap előbb-utóbb mást mondana.
  const kellPapir = projectCode.papir_kell !== false;
  const szerzodesKesz = projectCode.szerzodes_kell === false || projectCode.szerzodes_kesz === true;
  const tigKesz = projectCode.tig_kesz === true;
  // ELMARADT az esemény: ehhez semmit nem kérünk - se szerződést, se TIG-et,
  // se számlát. Ami nem történt meg, arról nincs mit igazolni (lásd backend
  // models/project_code.esemeny_elmaradt).
  const elmaradt = projectCode.elmaradt === true;
  // A SZÁMLA a papírozás harmadik lépése: akkor kerül sorra, ha a szerződés és
  // a TIG is megvan - ugyanaz a sorrend, mint az alvállalkozói oldalon.
  const szamlazhat = !elmaradt && (!kellPapir || (szerzodesKesz && tigKesz));
  const szamlak = attachments.filter((a) => a.kategoria === "szamla");

  // A bevétel a SZERVER száma (nem a bevétel-sorok itteni összege): így
  // ugyanaz áll itt, mint a listán, és beleszámít az is, ami ki van fizetve,
  // de szándékosan nem került a Pénzügyek bevételei közé (lásd backend
  // models/project_code.bevetel). Enélkül a bevétel nullát mutatott, miközben
  // a profit alatta már a valós összeget - ugyanarról a munkáról.
  const bevetel = szam(projectCode.bevetel);
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

        {/* Mind a három szám NETTÓ - a bevétel és a költség ugyanabban a
            szemléletben, különben a profit az ÁFA-tartalmak különbségével
            csúszna el (lásd backend services/elszamolas.py). */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard label="Bevétel (nettó)" value={formatHuf(bevetel)} icon={TrendingUp} tone="teal" />
          <StatCard
            label="Összes költség (nettó)"
            value={formatHuf(szam(projectCode.osszes_koltseg))}
            icon={TrendingDown}
            tone="orange"
          />
          <StatCard
            label="Becsült profit (nettó)"
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

        {/* MENNYIÉRT csináltuk. Külön, jól látható helyen, mert az összeget
            gyakran MÁS tudja, mint aki a papírokat készíti - eddig csak a
            szerződés/TIG űrlapján (vagy a mezőrács mélyén) lehetett megadni. */}
        <Card title="Mennyiért vállaltuk" icon={Wallet}>
          <VallalasiAr
            patchPath={`${ENTITY_PATHS.projectCode}/${projectCodeId}`}
            netto={typeof projectCode.netto_osszeg === "number" ? projectCode.netto_osszeg : null}
            pluszAfa={szoveg(projectCode.plusz_afa)}
            canEdit={canEdit}
            papirbolNetto={szamlaAllas?.netto ?? null}
          />
        </Card>

        {/* MEGRENDELŐI PAPÍROZÁS, három lépésben: szerződés → TIG → számla.
            Ugyanaz a sorrend, mint az alvállalkozói oldalon, és ugyanúgy a
            sorrend maga az információ: a számla addig nem nyílik meg, amíg az
            első kettő nincs meg - így ránézésre látszik, hol tart a munka. */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          <Card title="1. Megrendelői szerződés" icon={FileSignature}>
            {/* Keret alatt nincs eseti szerződés-teendő - de ezt KI KELL
                MONDANI a projektkódra, nem elég, hogy az ügyfélnek van
                valahol kerete (lásd KeretKotes). */}
            <div className="mb-3">
              <KeretKotes
                projectCodeId={projectCodeId}
                keretFedi={projectCode.keret_fedi === true}
                keretNeve={szoveg(projectCode.keretszerzodes_neve)}
                keretszerzodesId={typeof projectCode.contract_id === "number" ? projectCode.contract_id : null}
                keretek={megrendeloiKeretek}
                canEdit={canEdit}
              />
            </div>
            <MegrendeloiPapirKezelo
              projectCodeId={projectCodeId}
              fajta="szerzodes"
              papirok={megrendeloiSzerzodesek}
              ugyfelek={ugyfelek}
              kontaktok={megrendeloiKontaktok}
              canEdit={canEdit}
              canDelete={canDelete}
              kellPapir={kellPapir}
              nincsPapirOka={elmaradt ? "Az esemény elmaradt - erre a kódra nem kérünk papírt." : undefined}
            />
          </Card>
          <Card title="2. Megrendelői TIG" icon={FileCheck2}>
            <MegrendeloiPapirKezelo
              projectCodeId={projectCodeId}
              fajta="tig"
              papirok={megrendeloiTigek}
              ugyfelek={ugyfelek}
              kontaktok={megrendeloiKontaktok}
              canEdit={canEdit}
              canDelete={canDelete}
              kellPapir={kellPapir}
              nincsPapirOka={elmaradt ? "Az esemény elmaradt - erre a kódra nem kérünk papírt." : undefined}
            />
          </Card>
          <Card title="3. Számla" icon={Receipt}>
            {szamlazhat ? (
              <div className="space-y-3">
                <DokumentumFeltoltes
                  entityType="projectCode"
                  entityId={projectCodeId}
                  attachments={szamlak}
                  kategoria="szamla"
                  canEdit={canEdit}
                  canDelete={canDelete}
                  emptyText="Nincs feltöltött számla."
                />
                {/* A pénz útja: mikorra szól a számla, mikor jött meg, és
                    bekerül-e a Pénzügyek bevételei közé. */}
                {szamlaAllas && (
                  <div className="border-t border-border pt-3">
                    <MegrendeloiSzamla projectCodeId={projectCodeId} allas={szamlaAllas} canEdit={canEdit} />
                  </div>
                )}
              </div>
            ) : (
              // Nem tiltás, hanem sorrend: a számla a papírok után jön. Ha
              // valamiért mégis kell, a hiányzó papírt kell rendezni (vagy
              // kihagyni) - így a lépés nem marad nyom nélkül. Elmaradt
              // eseménynél viszont nincs mire várni: ott nincs miről számlázni.
              <div className="space-y-2">
                <p className="text-[13px] text-text-secondary">
                  {elmaradt
                    ? "Az esemény elmaradt - nincs miről számlázni."
                    : "Előbb a szerződés és a TIG - a számla utánuk jön."}
                </p>
                {!elmaradt && (
                  <div className="flex flex-wrap gap-2">
                    <StatusBadge
                      label={szerzodesKesz ? "Szerződés megvan" : "Szerződés hiányzik"}
                      tone={szerzodesKesz ? "success" : "warning"}
                    />
                    <StatusBadge label={tigKesz ? "TIG megvan" : "TIG hiányzik"} tone={tigKesz ? "success" : "warning"} />
                  </div>
                )}
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
              Nem a megszokott módon van elszámolva? (nincs szerződés / TIG / számla)
            </summary>
            <div className="mt-3">
              <p className="mb-3 text-[12.5px] text-text-secondary">
                Itt mondhatod ki, hogy erre a munkára nem kell papír – ilyenkor sem szerződést, sem TIG-et nem kérünk
                rá, és a számlához fizetési határidőt sem. A pénz oldalát a „3. Számla” kártya intézi: ott jelölhető,
                hogy nincs számla, és hogy kifizetve van-e (akár úgy is, hogy ne kerüljön a bevételek közé). Egy-egy
                papír külön is kihagyható, indokkal, a saját kártyáján.
              </p>
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
