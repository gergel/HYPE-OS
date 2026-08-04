import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { BelsosTigHaviAttekintes } from "@/components/BelsosTigHaviAttekintes";
import { BelsosTigManager } from "@/components/BelsosTigManager";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { getBelsosTigAttekintes, getBelsosTigMonth, getMyPagePermissions } from "@/lib/api";
import { huEvHonap } from "@/lib/huDate";

function shiftMonth(ev: number, honap: number, delta: number): { ev: number; honap: number } {
  const zeroBased = honap - 1 + delta;
  const newEv = ev + Math.floor(zeroBased / 12);
  const newHonap = ((zeroBased % 12) + 12) % 12;
  return { ev: newEv, honap: newHonap + 1 };
}

/** Belsős TIG - önálló, NEM projekthez kötött admin oldal (lásd
 * backend/app/api/routes/internal_performance_certificates.py fejléc-
 * kommentje): alapértelmezetten a folyó hónapot mutatja, és felsorolja AZ
 * ÖSSZES belsős munkatársat, akiknek havonta pontosan egy TIG-et kell
 * készíteni (vagy admin kihagyja őket az adott hónapból, ha épp nem
 * dolgoztak). Ellentétben a Külsős TIG-gel, ez sosem projektenkénti. */
export default async function BelsosTigPage({
  searchParams,
}: {
  searchParams: Promise<{ ev?: string; honap?: string }>;
}) {
  const params = await searchParams;
  const today = new Date();
  const ev = params.ev ? Number(params.ev) : today.getFullYear();
  const honap = params.honap ? Number(params.honap) : today.getMonth() + 1;

  const [employees, attekintes, pagePermissions] = await Promise.all([
    getBelsosTigMonth(ev, honap),
    getBelsosTigAttekintes(12),
    getMyPagePermissions(),
  ]);
  // Aki az oldalon szerkeszthet, az az állapotot is kézzel át tudja állítani.
  const canEdit = pagePermissions === null || !!pagePermissions["/belsos-tig"]?.includes("edit");
  const prev = shiftMonth(ev, honap, -1);
  const next = shiftMonth(ev, honap, 1);

  // A "Kész" a korábbi, email-küldés nélküli életciklusból maradt állapot -
  // a régi bejegyzések így vannak eltárolva (lásd backend TERMINAL_STATUSES).
  const kikuldveCount = employees.filter(
    (e) => e.record?.allapot === "Kiküldve" || e.record?.allapot === "Kész",
  ).length;
  const kihagyvaCount = employees.filter((e) => e.record?.allapot === "Kihagyva").length;
  const teendoCount = employees.length - kikuldveCount - kihagyvaCount;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-8">
        {/* Havi "mappázás": hónaponként külön dobozban, hogy ne folyjanak
            egybe - melyik hónap van kész, és ahol nincs, ott kinek mi
            hiányzik, meddig (lásd BelsosTigHaviAttekintes). */}
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
          <p className="mb-4 text-[13px] text-text-secondary">
            {employees.length} belsős munkatárs · {kikuldveCount} kiküldve · {kihagyvaCount} kihagyva · {teendoCount} még
            teendő
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
