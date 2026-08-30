import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { DokumentumFeltoltes } from "@/components/DokumentumFeltoltes";
import { KoltsegBontas } from "@/components/KoltsegBontas";
import { KeretKotes } from "@/components/megrendeloi/KeretKotes";
import { MegrendeloiPapirKezelo } from "@/components/megrendeloi/MegrendeloiPapirKezelo";
import { MegrendeloiSzamla } from "@/components/megrendeloi/MegrendeloiSzamla";
import { PapirKapcsolok } from "@/components/megrendeloi/PapirKapcsolok";
import { CommentsSection } from "@/components/projektkod/CommentsSection";
import { AlvallalkozoiPapirokAttekintes } from "@/components/projektkod/AlvallalkozoiPapirokAttekintes";
import { ProjektkodBontasTablak } from "@/components/projektkod/ProjektkodBontasTablak";
import { VallalasiAr } from "@/components/projektkod/VallalasiAr";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  formatHuf,
  getAllContractsForProjectCode,
  getAllTigForProjectCode,
  getAttachments,
  getClients,
  getCurrentUser,
  getEmployees,
  getMegbizasTargyaLista,
  getMegrendeloiKeretek,
  getMegrendeloiKontaktok,
  getMegrendeloiPapirok,
  getMegrendeloiSzamlaAllas,
  getMyPagePermissions,
  getPendingSubcontractorsForProjectCode,
  getPendingTigForProjectCode,
  getProjectCodeComments,
  getProjektkodBontas,
  getRecord,
} from "@/lib/api";
import { bevetelDevizaNyom } from "@/lib/penz";
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

/** A devizás bevétel eredete a nyers rekordból (lásd backend
 * models/project_code.bevetel_deviza). A mező hiányozhat - régi válaszban, és
 * minden forintos munkán -, ezért itt ellenőrizzük, nem a megjelenítésnél. */
function bevetelDeviza(ertek: unknown): { penznem: string; netto: number; arfolyam: number | null } | null {
  if (!ertek || typeof ertek !== "object") return null;
  const d = ertek as { penznem?: unknown; netto?: unknown; arfolyam?: unknown };
  if (typeof d.penznem !== "string" || typeof d.netto !== "number") return null;
  return { penznem: d.penznem, netto: d.netto, arfolyam: typeof d.arfolyam === "number" ? d.arfolyam : null };
}

export default async function ProjectCodeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projectCodeId = Number(id);

  const [
    projectCode,
    megrendeloiSzerzodesek,
    megrendeloiTigek,
    megrendeloiKeretek,
    megrendeloiKontaktok,
    megbizasTargyaLista,
    clients,
    bontas,
    pagePermissions,
    currentUser,
    attachments,
    szamlaAllas,
    comments,
    employees,
    pendingSzerzodes,
    pendingTig,
    keszSzerzodesek,
    keszTigek,
  ] = await Promise.all([
    // Egyik lenti hívás sem függ a projektkód rekord mezőitől, csak a
    // projectCodeId-tól (ami az URL-ből már megvan) - ezért ez is a közös
    // Promise.all-ba kerül, nem külön await-tel előtte: egy kevesebb kör az
    // oldalbetöltésnél.
    getRecord(ENTITY_PATHS.projectCode, projectCodeId),
    // A megrendelői papírok (lásd backend routes/megrendeloi_papirok.py): a
    // szerződő fél a MEGRENDELŐK közül választható, a kapcsolattartó pedig a
    // megrendelői kontaktokból - ezért kell mindkét lista a szerkesztőhöz.
    // A keretszerződések listája a keret-kötéshez kell (KeretKotes).
    getMegrendeloiPapirok("szerzodes", projectCodeId),
    getMegrendeloiPapirok("tig", projectCodeId),
    getMegrendeloiKeretek(),
    getMegrendeloiKontaktok(),
    // A "Megbízás tárgya" mező legördülő javaslatlistája - eddig előfordult
    // szövegek, hogy ne kelljen mindig ugyanazt begépelni.
    getMegbizasTargyaLista(),
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
    // Hozzászólások - ugyanaz a chat-szerű minta, mint az Utómunkánál (lásd
    // components/projektkod/CommentsSection.tsx).
    getProjectCodeComments(projectCodeId),
    // A "@" taggeléshez: a Project Code-nak nincs saját "kioszthatók" listája
    // (mint az Utómunkának), ezért az egész munkatárs-listát ajánljuk fel.
    getEmployees(),
    // ALVÁLLALKOZÓI szerződés/TIG - PROJEKTKÓDHOZ kötve, forgatás nélkül
    // (tisztán ügynökségi feladat, lásd backend "projektkód-szintű ág"). Ez
    // MÁS, mint a fenti "Megrendelői" papírozás: ott mi vagyunk a
    // megbízott, itt egy alvállalkozónak fizetünk.
    getPendingSubcontractorsForProjectCode(projectCodeId),
    getPendingTigForProjectCode(projectCodeId),
    getAllContractsForProjectCode(projectCodeId),
    getAllTigForProjectCode(projectCodeId),
  ]);
  if (!projectCode) notFound();

  const ugyfelek = clients
    .map((c) => ({ id: c.id, nev: c.nev }))
    .sort((a, b) => a.nev.localeCompare(b.nev, "hu"));

  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  // Az alvállalkozói szerződés/TIG törlése az Utókövetés jogára hallgat, nem
  // a Project Code oldaléra - ugyanaz a jog, mint magán az Utókövetésen
  // (lásd backend subcontractor_contracts.py PAGE = "/utokovetes").
  const torolhetAlvallalkozoiPapirt = canDoAction(currentUser, pagePermissions, "/utokovetes", "delete");
  // A forint összegek a Pénzügy-hozzáféréshez kötöttek - ugyanaz a szabály,
  // mint a forgatás adatlapján (lásd ProjektPapirokEsKoltsegek).
  const lathatKoltseget = pagePermissions === null || !!pagePermissions["/penzugyek"]?.includes("view");
  // A tételes bontás sorai a SAJÁT végpontjukon törlődnek, tehát a saját
  // oldaluk jogosultsága kell hozzájuk - nem a projektkódé. Így a gomb csak
  // ott jelenik meg, ahol a szerver is engedné (lásd ProjektkodBontasTablak).
  const torolhetForgatast = canDoAction(currentUser, pagePermissions, "/projektek", "delete");
  const torolhetUtomunkat = canDoAction(currentUser, pagePermissions, "/utomunka", "delete");
  const torolhetKiadast = canDoAction(currentUser, pagePermissions, "/penzugyek", "delete");
  // A kiadás-sorok helyben szerkeszthetők a bontás-táblában - ugyanaz a jog
  // kell hozzá, mint a saját oldalukon (Pénzügyek).
  const szerkesztheiKiadast = canDoAction(currentUser, pagePermissions, "/penzugyek", "edit");

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
  // Milyen pénznemben vállaltuk: a papírokon (szerződés, TIG) EZ az összeg áll,
  // mert abban állapodtunk meg. A bevétel ettől még forintban keletkezik
  // (lásd backend services/penznem.py).
  const penznemKod = typeof projectCode.penznem === "string" && projectCode.penznem ? projectCode.penznem : "HUF";
  const szamlak = attachments.filter((a) => a.kategoria === "szamla");

  // A bevétel a SZERVER száma (nem a bevétel-sorok itteni összege): így
  // ugyanaz áll itt, mint a listán, és beleszámít az is, ami ki van fizetve,
  // de szándékosan nem került a Pénzügyek bevételei közé (lásd backend
  // models/project_code.bevetel). Enélkül a bevétel nullát mutatott, miközben
  // a profit alatta már a valós összeget - ugyanarról a munkáról.
  const bevetel = szam(projectCode.bevetel);
  const profit = szam(projectCode.becsult_profit);
  // A három szám FORINTBAN áll, devizás munkán is - a könyvelésünk abban vezet.
  // Devizánál viszont oda kell írni, miből lett, mert egy át NEM váltott összeg
  // ugyanúgy néz ki, mint egy szokásos forintos (lásd lib/penz.bevetelDevizaNyom).
  // A papírokra (szerződés, TIG) továbbra is az EREDETI pénznem kerül: azon az
  // szerepel, amiben megállapodtunk.
  const devizaNyoma = bevetelDevizaNyom(bevetelDeviza(projectCode.bevetel_deviza));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
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
          <StatCard
            label="Bevétel (nettó)"
            value={formatHuf(bevetel)}
            icon={TrendingUp}
            tone="teal"
            megjegyzes={devizaNyoma ?? undefined}
          />
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
            penznem={penznemKod}
            arfolyam={typeof projectCode.arfolyam === "number" ? projectCode.arfolyam : null}
            magyarazat={szoveg(projectCode.vallalasi_ar_magyarazat)}
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
              megbizasTargyaLista={megbizasTargyaLista}
              canEdit={canEdit}
              canDelete={canDelete}
              kellPapir={kellPapir}
              nincsPapirOka={elmaradt ? "Az esemény elmaradt - erre a kódra nem kérünk papírt." : undefined}
              penznem={penznemKod}
            />
          </Card>
          <Card title="2. Megrendelői TIG" icon={FileCheck2}>
            <MegrendeloiPapirKezelo
              projectCodeId={projectCodeId}
              fajta="tig"
              papirok={megrendeloiTigek}
              ugyfelek={ugyfelek}
              kontaktok={megrendeloiKontaktok}
              megbizasTargyaLista={megbizasTargyaLista}
              canEdit={canEdit}
              canDelete={canDelete}
              kellPapir={kellPapir}
              nincsPapirOka={elmaradt ? "Az esemény elmaradt - erre a kódra nem kérünk papírt." : undefined}
              penznem={penznemKod}
            />
          </Card>
          <Card title="3. Számla" icon={Receipt}>
            <div className="space-y-3">
              {/* Ha már ki van mondva, hogy erről a munkáról NEM lesz számla
                  (lásd MegrendeloiSzamla "Nincs számla erről a munkáról"
                  gombja, indokkal), a feltöltő "Nincs feltöltött számla."
                  nyugtalanító sora és a gombja fölösleges - épp az van alatta
                  kiírva, hogy miért nem is lesz. Csak akkor marad némán
                  eltüntetve, ha tényleg nincs is feltöltött fájl - ha
                  valahogy mégis van (pl. a döntés előtt feltöltötték), az
                  továbbra is látszik és szerkeszthető. */}
              {!(szamlaAllas?.szamla_kihagyva && szamlak.length === 0) && (
                <DokumentumFeltoltes
                  entityType="projectCode"
                  entityId={projectCodeId}
                  attachments={szamlak}
                  kategoria="szamla"
                  canEdit={canEdit}
                  canDelete={canDelete}
                  emptyText="Nincs feltöltött számla."
                  // Osztott számlázásnál egy kódhoz több számla is tartozhat -
                  // ezért minden egyes feltöltött fájlnak KÜLÖN adható meg a
                  // fizetési határideje és a kifizetés dátuma (lásd
                  // components/DokumentumFeltoltes.tsx).
                  fizetesiAllapot
                  penznem={penznemKod}
                />
              )}
              {/* A SZÁMLA-LÉPÉS SEM VÁR A PAPÍROKRA. Korábban a fizetési
                  határidő és a "Kifizetve" jelölés csak a szerződés és a TIG
                  után nyílt meg - de a pénz nem tartja magát ehhez a
                  sorrendhez: a számla kimehet és be is jöhet a pénz úgy, hogy
                  a papírok még senkinél nincsenek aláírva. Amíg ezt nem
                  lehetett rögzíteni, épp a legelakadtabb munkákról nem
                  látszott, hogy a határidejük lejárt.

                  A SORREND attól még sorrend: alatta ott a jelzés, mi hiányzik
                  még - csak nem tiltás, hanem emlékeztető. */}
              {szamlaAllas && (
                <div className={szamlaAllas.szamla_kihagyva && szamlak.length === 0 ? "" : "border-t border-border pt-3"}>
                  <MegrendeloiSzamla projectCodeId={projectCodeId} allas={szamlaAllas} canEdit={canEdit} />
                </div>
              )}
              {/* Elmaradt eseménynél nincs miről számlázni - ezt kimondjuk, de
                  a mezőket akkor sem zárjuk el: ha mégis volt lemondási díj,
                  azt is rögzíteni kell tudni. */}
              {(elmaradt || !szerzodesKesz || !tigKesz) && (
                <div className="space-y-2 border-t border-border pt-3">
                  {elmaradt ? (
                    <p className="text-[13px] text-text-secondary">
                      Az esemény elmaradt – erre a kódra nem kérünk papírt.
                    </p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      <StatusBadge
                        label={szerzodesKesz ? "Szerződés megvan" : "Szerződés hiányzik"}
                        tone={szerzodesKesz ? "success" : "warning"}
                      />
                      <StatusBadge label={tigKesz ? "TIG megvan" : "TIG hiányzik"} tone={tigKesz ? "success" : "warning"} />
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* ALVÁLLALKOZÓI papírozás, FORGATÁS NÉLKÜL: ha egy projekt-kiadáson
            valakit alvállalkozóként jelöltek meg, de a kiadáshoz nincs
            konkrét forgatás (tisztán ügynökségi feladat), a szerződés és a
            TIG közvetlenül ehhez a projektkódhoz kötve készül - NEM jön
            létre hozzá "helyettesítő" forgatás (lásd backend
            subcontractor_contracts.py / performance_certificates.py
            "projektkód-szintű ág").

            Ez a blokk itt csak NÉZET - ugyanaz az elv, mint a forgatás
            adatlapján (lásd ProjektPapirokEsKoltsegek): a papírozás művelete
            (mentés, generálás, küldés, kihagyás, törlés) az Utókövetésen
            történik, más kézben és gyakran több projektkódra rálátva - nem
            itt, a projekt/kiadás adatlapján. Csak akkor jelenik meg, ha van
            is mit mutatni - a legtöbb projektkódnál nincs ilyen kiadás. */}
        {((pendingSzerzodes?.pending.length ?? 0) > 0 ||
          (pendingTig?.pending.length ?? 0) > 0 ||
          (pendingTig?.szerzodesre_varo.length ?? 0) > 0 ||
          keszSzerzodesek.length > 0 ||
          keszTigek.length > 0) && (
          <AlvallalkozoiPapirokAttekintes
            projectCodeId={projectCodeId}
            szerzodesek={keszSzerzodesek}
            tigek={keszTigek}
            lathatKoltseget={lathatKoltseget}
            canDelete={torolhetAlvallalkozoiPapirt}
          />
        )}

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
          <ProjektkodBontasTablak
            bontas={bontas}
            projectCodeId={projectCodeId}
            employees={employees}
            torolhetForgatast={torolhetForgatast}
            torolhetUtomunkat={torolhetUtomunkat}
            torolhetKiadast={torolhetKiadast}
            szerkesztheiKiadast={szerkesztheiKiadast}
          />
        ) : (
          <Card title="Költségek tételesen">
            <p className="text-[13px] text-text-secondary">A bontás most nem érhető el.</p>
          </Card>
        )}

        {/* HOZZÁSZÓLÁSOK - ugyanaz a chat-szerű minta, mint az Utómunkánál. */}
        <Card title="Hozzászólások">
          <CommentsSection
            projectCodeId={projectCodeId}
            initialComments={comments}
            mentionableEmployees={employees.map((e) => ({ id: e.id, full_name: e.full_name }))}
          />
        </Card>
      </div>
    </div>
  );
}
