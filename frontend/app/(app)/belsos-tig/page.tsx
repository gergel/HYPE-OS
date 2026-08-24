import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { BelsosTigHaviAttekintes } from "@/components/BelsosTigHaviAttekintes";
import { BelsosTigManager } from "@/components/BelsosTigManager";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import {
  getBelsosIdoszakHianyzik,
  getBelsosTigAttekintes,
  getBelsosTigMonth,
  getMyPagePermissions,
} from "@/lib/api";
import { huDatum, huEvHonap } from "@/lib/huDate";

function shiftMonth(ev: number, honap: number, delta: number): { ev: number; honap: number } {
  const zeroBased = honap - 1 + delta;
  const newEv = ev + Math.floor(zeroBased / 12);
  const newHonap = ((zeroBased % 12) + 12) % 12;
  return { ev: newEv, honap: newHonap + 1 };
}

/** Belsős TIG - önálló, NEM projekthez kötött admin oldal (lásd
 * backend/app/api/routes/internal_performance_certificates.py fejléc-
 * kommentje): felsorolja AZ ÖSSZES belsős munkatársat, akiknek havonta
 * pontosan egy TIG-et kell készíteni (vagy admin kihagyja őket az adott
 * hónapból, ha épp nem dolgoztak). Ellentétben a Külsős TIG-gel, ez sosem
 * projektenkénti.
 *
 * A TIG-ek VISSZAFELÉ készülnek: mindig az előző hónapé az, amit épp
 * csinálunk (júliusban a júniusi, augusztusban a júliusi), ezért az oldal
 * alapból az ELŐZŐ hónapot nyitja meg - a folyó hónap csak a nyilakkal. */
export default async function BelsosTigPage({
  searchParams,
}: {
  searchParams: Promise<{ ev?: string; honap?: string }>;
}) {
  const params = await searchParams;
  const today = new Date();
  const alap = shiftMonth(today.getFullYear(), today.getMonth() + 1, -1);
  const ev = params.ev ? Number(params.ev) : alap.ev;
  const honap = params.honap ? Number(params.honap) : alap.honap;

  const [employees, attekintes, idoszakHianyzik, pagePermissions] = await Promise.all([
    getBelsosTigMonth(ev, honap),
    getBelsosTigAttekintes(12),
    getBelsosIdoszakHianyzik(),
    getMyPagePermissions(),
  ]);
  // Aki az oldalon szerkeszthet, az az állapotot is kézzel át tudja állítani.
  const canEdit = pagePermissions === null || !!pagePermissions["/belsos-tig"]?.includes("edit");
  const prev = shiftMonth(ev, honap, -1);
  const next = shiftMonth(ev, honap, 1);

  // A bejelentett alkalmazottakat külön számoljuk: náluk nincs TIG, a havi
  // teendő csak a fizetés beírása (lásd backend BelsosJogviszony).
  const tigesek = employees.filter((e) => e.kell_tig);
  const alkalmazottak = employees.filter((e) => !e.kell_tig);
  // A "Kész" a korábbi, email-küldés nélküli életciklusból maradt állapot -
  // a régi bejegyzések így vannak eltárolva (lásd backend TERMINAL_STATUSES).
  const kikuldveCount = tigesek.filter(
    (e) => e.record?.allapot === "Kiküldve" || e.record?.allapot === "Kész",
  ).length;
  const kihagyvaCount = employees.filter((e) => e.record?.allapot === "Kihagyva").length;
  const teendoCount = tigesek.length - kikuldveCount - tigesek.filter((e) => e.record?.allapot === "Kihagyva").length;
  const fizetesHianyzik = alkalmazottak.filter(
    (e) => e.record?.allapot !== "Kihagyva" && (e.record?.netto_osszeg == null || e.record.netto_osszeg === 0),
  ).length;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        {/* Havi "mappázás": hónaponként külön dobozban, hogy ne folyjanak
            egybe - melyik hónap van kész, és ahol nincs, ott kinek mi
            hiányzik, meddig (lásd BelsosTigHaviAttekintes). */}
        {/* A havi listák időszak nélkül nem találgatnak: aki nincs felvezetve,
            az nem is jelenik meg. Ez csak akkor biztonságos, ha a hiány
            LÁTSZIK - különben egy elfelejtett időszak miatt csendben kimaradna
            valakinek a havi TIG-je. */}
        {idoszakHianyzik.length > 0 && (
          <div className="rounded-[var(--radius)] border border-border bg-bg-warning px-4 py-3">
            <p className="text-[13px] font-medium text-text-warning">
              {idoszakHianyzik.length} belsősnél nincs megadva a belsős időszak
            </p>
            <p className="mt-1 text-[12.5px] text-text-secondary">
              Amíg nincs megadva, hogy mettől meddig belsős, a havi listákon csak onnantól jelenik meg, ahonnan
              van róla bejegyzés – akiről semmi sincs, az egyik hónapon sem. Az időszakot a munkatárs adatlapján
              lehet felvinni.
            </p>
            <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12.5px]">
              {idoszakHianyzik.map((e) => (
                <li key={e.employee_id}>
                  <a href={`/csapat/${e.employee_id}`} className="text-text-accent hover:underline">
                    {e.full_name}
                  </a>
                  <span className="ml-1 text-text-muted">
                    {e.nyom_kezdet ? `(${huDatum(e.nyom_kezdet)}-tól számítva)` : "(nincs róla bejegyzés)"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <Card title="Havi áttekintés">
          <BelsosTigHaviAttekintes honapok={attekintes} />
        </Card>

        <Card
          title={`Belsős TIG – ${huEvHonap(ev, honap)}`}
          actions={
            <div className="flex items-center gap-1">
              <Link
                href={`/belsos-tig?ev=${prev.ev}&honap=${prev.honap}`}
                className="rounded-[var(--radius)] border border-border p-1.5 text-text-secondary hover:bg-surface-3"
              >
                <ChevronLeft size={16} />
              </Link>
              <Link
                href={`/belsos-tig?ev=${next.ev}&honap=${next.honap}`}
                className="rounded-[var(--radius)] border border-border p-1.5 text-text-secondary hover:bg-surface-3"
              >
                <ChevronRight size={16} />
              </Link>
            </div>
          }
        >
          {/* Csak azok, akik EBBEN a hónapban belsősök voltak - ki mettől
              meddig, azt a munkatárs saját adatlapján lehet megadni (Csapat >
              az illető lapja > Belsős időszak). */}
          <p className="mb-4 text-[13px] text-text-secondary">
            {employees.length} belsős munkatárs · {kikuldveCount} kiküldve · {kihagyvaCount} kihagyva · {teendoCount} még
            teendő
            {alkalmazottak.length > 0 && (
              <>
                {" · "}
                {alkalmazottak.length} bejelentett alkalmazott
                {fizetesHianyzik > 0 ? ` (${fizetesHianyzik} fizetés hiányzik)` : " (fizetés beírva)"}
              </>
            )}
          </p>
          {employees.length === 0 ? (
            <p className="text-[13px] text-text-secondary">Nincs belsős munkatárs.</p>
          ) : (
            <BelsosTigManager ev={ev} honap={honap} employees={employees} canEdit={canEdit} />
          )}
        </Card>
      </div>
    </div>
  );
}
