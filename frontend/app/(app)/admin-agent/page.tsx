import Link from "next/link";
import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AdminAgentTabs } from "@/components/admin-agent/AdminAgentTabs";
import { AdminAgentSafetyBanner } from "@/components/admin-agent/AdminAgentSafetyBanner";
import { ALLAPOT_CIMKE } from "@/components/admin-agent/allapotok";
import { getAdminAgentOverview, getMyPagePermissions } from "@/lib/api";

const PAGE = "/admin-agent";

/** Lara — ÁTTEKINTÉS.
 *
 * Az adminisztrációs munkát (számla-felvezetés, e-mail-válasz, TIG- és
 * szerződés-előkészítés) önállóan kezelő Lara vezérlő-
 * pultja. Biztonságos alapállás: a modul KI, a mellékhatások TILTVA, minden
 * feladat L0 (árnyék) — lásd backend admin_agent/policy.py. Utalással Lara
 * nem foglalkozik (se végrehajtás, se előkészítés) — az a Pénzügyek dolga. */
export default async function AdminAgentAttekintesPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");

  const overview = await getAdminAgentOverview();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <AdminAgentTabs />

        {overview === null ? (
          <Card title="Áttekintés">
            <p className="text-[13px] text-text-secondary">
              Az áttekintő adatok most nem érhetők el. Töltsd újra az oldalt egy kicsit később.
            </p>
          </Card>
        ) : (
          <>
            <AdminAgentSafetyBanner modul={overview.modul} />

            <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <StatKartya cimke="Nyitott feladat" ertek={overview.nyitott} />
              <StatKartya
                cimke="Lejárt határidő"
                ertek={overview.lejart}
                hangsuly={overview.lejart > 0 ? "danger" : undefined}
              />
              <StatKartya cimke="Jóváhagyásra vár" ertek={overview.varakozo_jovahagyas} />
            </div>

            {overview.tanulas && (
              <Card title="Tanulás állapota" className="mb-6">
                <p className="mb-3 text-[12px] text-text-muted">
                  {overview.tanulas.megfigyeles_bekapcsolva
                    ? "A megfigyelés be van kapcsolva: Lara félóránként figyeli a projektkódokat és az utókövetést, éjszaka tanul."
                    : "A megfigyelés ki van kapcsolva (Beállítások → „Tanulás és megfigyelés”). Kézzel a Tanulás és minőség oldalról indítható."}
                  {overview.tanulas.tanulas_kezdete &&
                    ` Tanulás kezdete: ${overview.tanulas.tanulas_kezdete.replaceAll("-", ". ")}. — csak az azóta a HYPE OS-ben keletkezett munkából tanul.`}
                  {!!overview.tanulas.felretett_regi_jeloltek &&
                    ` ${overview.tanulas.felretett_regi_jeloltek} régi (Notion-korszakbeli) jelölt félretéve.`}
                </p>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
                  <TanulasSzam cimke="Megfigyelt lépés" ertek={overview.tanulas.megfigyelt_lepesek} href="/admin-agent/naplo" />
                  <TanulasSzam cimke="Emberi javítás" ertek={overview.tanulas.javitasok} href="/admin-agent/tanulas" />
                  <TanulasSzam cimke="Példa-jelölt" ertek={overview.tanulas.pelda_jeloltek} href="/admin-agent/tudastar" kiemel />
                  <TanulasSzam cimke="Szabály-jelölt" ertek={overview.tanulas.szabaly_jeloltek} href="/admin-agent/tudastar" kiemel />
                  <TanulasSzam cimke="Jóváhagyott példa" ertek={overview.tanulas.jovahagyott_peldak} href="/admin-agent/tudastar" />
                  <TanulasSzam cimke="Aktív szabály" ertek={overview.tanulas.aktiv_szabalyok} href="/admin-agent/tudastar" />
                  <TanulasSzam
                    cimke="Lara kérdései"
                    ertek={overview.tanulas.nyitott_kerdesek ?? 0}
                    href="/admin-agent/kerdesek"
                    kiemel
                  />
                </div>
              </Card>
            )}

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card title="Feladatok állapot szerint">
                <AllapotBontas bontas={overview.allapot_bontas} />
              </Card>

              <Card title="Forráskapcsolatok">
                {overview.integraciok && overview.integraciok.length > 0 ? (
                  <ul className="flex flex-col gap-2">
                    {overview.integraciok.map((i) => {
                      const kesz = i.allapot === "kesz";
                      return (
                        <li key={i.kulcs} className="flex items-start justify-between gap-3 text-[13px]">
                          <div>
                            <p className="text-text-primary">{i.nev}</p>
                            {!kesz && i.uzenet && <p className="text-[12px] text-text-muted">{i.uzenet}</p>}
                          </div>
                          <span
                            className={`shrink-0 rounded-[var(--radius)] px-2 py-0.5 text-[12px] font-medium ${
                              kesz ? "bg-bg-success text-text-success" : "bg-bg-warning text-text-warning"
                            }`}
                          >
                            {kesz ? "Kész" : "Beállítás szükséges"}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p className="text-[13px] text-text-secondary">Nincs információ a forráskapcsolatokról.</p>
                )}
              </Card>

              <Card title="Mért mutatók">
                {overview.eleg_adat ? (
                  <div className="grid grid-cols-2 gap-3">
                    <MertMutato cimke="Ember nélkül lezárt" ertek={overview.ember_nelkul_lezart} />
                    <MertMutato
                      cimke="Elfogadási arány"
                      ertek={overview.elfogadasi_arany}
                      formatum="szazalek"
                    />
                    <MertMutato cimke="Kritikus hiba" ertek={overview.kritikus_hibak} />
                    <MertMutato
                      cimke="Modellköltség"
                      ertek={overview.modell_koltseg_mikro}
                      formatum="mikro_penz"
                    />
                  </div>
                ) : (
                  <div className="rounded-[var(--radius)] border border-dashed border-border px-4 py-6 text-center">
                    <p className="text-[13px] text-text-secondary">Még nincs elég adat</p>
                    <p className="mt-1 text-[12px] text-text-muted">
                      A minőségi mutatók (ember nélkül lezárt arány, elfogadási arány, kritikus hibák, modellköltség)
                      akkor jelennek meg, amikor Lara éles feladatokat kezdett feldolgozni és a mérőrendszer
                      elegendő eseményt gyűjtött.
                    </p>
                  </div>
                )}
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StatKartya({
  cimke,
  ertek,
  hangsuly,
}: {
  cimke: string;
  ertek: number;
  hangsuly?: "danger";
}) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface-2 px-4 py-3.5">
      <p className="text-[12px] text-text-muted">{cimke}</p>
      <p
        className={`mt-1 text-[24px] font-semibold leading-none ${
          hangsuly === "danger" ? "text-text-danger" : "text-text-primary"
        }`}
      >
        {ertek}
      </p>
    </div>
  );
}

function TanulasSzam({
  cimke,
  ertek,
  href,
  kiemel,
}: {
  cimke: string;
  ertek: number;
  href: string;
  kiemel?: boolean;
}) {
  return (
    <Link
      href={href}
      className="rounded-[var(--radius)] bg-surface-3 px-3 py-2.5 transition-colors hover:bg-surface-4"
    >
      <p className="text-[11.5px] text-text-muted">{cimke}</p>
      <p className={`mt-0.5 text-[18px] font-semibold ${kiemel && ertek > 0 ? "text-text-accent" : "text-text-primary"}`}>
        {ertek}
      </p>
    </Link>
  );
}

function AllapotBontas({ bontas }: { bontas: Record<string, number> }) {
  const sorok = Object.entries(bontas)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1]);
  if (sorok.length === 0) {
    return <p className="text-[13px] text-text-secondary">Még nincs egyetlen feladat sem.</p>;
  }
  return (
    <ul className="flex flex-col gap-1.5">
      {sorok.map(([allapot, n]) => (
        <li key={allapot} className="flex items-center justify-between text-[13px]">
          <span className="text-text-secondary">{ALLAPOT_CIMKE[allapot] ?? allapot}</span>
          <span className="font-medium text-text-primary">{n}</span>
        </li>
      ))}
    </ul>
  );
}

function MertMutato({
  cimke,
  ertek,
  formatum,
}: {
  cimke: string;
  ertek: number | null;
  formatum?: "szazalek" | "mikro_penz";
}) {
  let megjelenit = "—";
  if (ertek !== null) {
    if (formatum === "szazalek") megjelenit = `${Math.round(ertek * 100)}%`;
    else if (formatum === "mikro_penz") megjelenit = `${Math.round(ertek / 1_000_000).toLocaleString("hu-HU")} Ft`;
    else megjelenit = ertek.toLocaleString("hu-HU");
  }
  return (
    <div className="rounded-[var(--radius)] bg-surface-3 px-3 py-2.5">
      <p className="text-[11.5px] text-text-muted">{cimke}</p>
      <p className="mt-0.5 text-[16px] font-semibold text-text-primary">{megjelenit}</p>
    </div>
  );
}
