import Link from "next/link";
import { redirect } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { RendezesSorok } from "@/components/belsos-tig/RendezesSorok";
import { getBelsosTigRendezes, getCurrentUser, getMyPagePermissions, type BelsosRendezesHonap } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";
import { formatHuf } from "@/lib/penz";

const PAGE = "/belsos-tig";
const ROVID = ["jan", "feb", "már", "ápr", "máj", "jún", "júl", "aug", "szep", "okt", "nov", "dec"];

/** Egy cella jelzései az összesítőben: mi hiányzik még a hónapból. */
function hiany(m: BelsosRendezesHonap): string[] {
  if (m.tig_id === null) return m.belsos ? ["nincs TIG"] : [];
  if (m.allapot === "Kihagyva") return [];
  const ki: string[] = [];
  if (m.kell_tig && !m.tig_fajl_url) ki.push("TIG");
  if (m.kell_tig && m.szamlak.length === 0) ki.push("számla");
  if (!m.szamla_kifizetve) ki.push("kifizetés");
  return ki;
}

/** BELSŐS TIG – VISSZAMENŐLEGES RENDEZÉS (a felhasználó kérése): egy év
 * minden belsőse, hónaponként. Felül az összesítő (ki mikor mennyit
 * keresett, és mi hiányzik még), alatta munkatársanként a hónapok a
 * rendezés műveleteivel: összeg, TIG feltöltése kiküldés helyett, számlák,
 * kifizetve jelölés Kiadás sor nélkül, és az elcsúszott hónap áthelyezése. */
export default async function BelsosTigRendezesPage({
  searchParams,
}: {
  searchParams: Promise<{ ev?: string }>;
}) {
  const sp = await searchParams;
  const ev = Number(sp.ev) || new Date().getFullYear();
  const [pagePermissions, currentUser] = await Promise.all([getMyPagePermissions(), getCurrentUser()]);
  if (pagePermissions !== null && !pagePermissions[PAGE]?.includes("view")) redirect("/nincs-jogosultsag");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  const sorok = await getBelsosTigRendezes(ev);
  const evOsszesen = sorok.reduce((s, r) => s + r.osszesen, 0);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        <BackLink href="/belsos-tig" label="Belsős TIG" />
        <Card
          title={`Visszamenőleges rendezés – ${ev}`}
          actions={
            <div className="flex items-center gap-1">
              <Link href={`/belsos-tig/rendezes?ev=${ev - 1}`} className="rounded-[var(--radius)] border border-border p-1.5 text-text-secondary hover:bg-surface-3">
                <ChevronLeft size={16} />
              </Link>
              <Link href={`/belsos-tig/rendezes?ev=${ev + 1}`} className="rounded-[var(--radius)] border border-border p-1.5 text-text-secondary hover:bg-surface-3">
                <ChevronRight size={16} />
              </Link>
            </div>
          }
        >
          <p className="mb-4 text-[13px] text-text-secondary">
            Ki mikor mennyit keresett ({sorok.length} munkatárs, összesen {formatHuf(evOsszesen)}). A cellában a hónap
            nettó összege, alatta, ha még hiányzik valami. A régi hónapoknál a TIG-et nem kell kiküldeni: elég feltölteni,
            és a kifizetés úgy jelölhető, hogy a Kiadások közé nem kerül újra. Az elcsúszott hónap a munkatárs
            sorainál helyezhető át (a dátumai alapján jelezzük, ha másik hónapra mutatnak).
          </p>
          {sorok.length === 0 ? (
            <p className="text-[13px] text-text-muted">Ebben az évben nincs belsős munkatárs és belsős TIG.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="os-table min-w-full border-collapse text-[12.5px]">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-1.5 pr-3 text-left font-medium text-text-secondary">Munkatárs</th>
                    {ROVID.map((r) => (
                      <th key={r} className="px-1.5 py-1.5 text-right font-medium text-text-secondary">{r}</th>
                    ))}
                    <th className="py-1.5 pl-3 text-right font-medium text-text-secondary">Év</th>
                  </tr>
                </thead>
                <tbody>
                  {sorok.map((s) => (
                    <tr key={s.employee_id} className="border-b border-border last:border-0">
                      <td className="py-1.5 pr-3">
                        <a href={`#e${s.employee_id}`} className="text-text-accent hover:underline">{s.full_name}</a>
                      </td>
                      {s.honapok.map((m) => {
                        const h = hiany(m);
                        const elcsuszott = Object.keys(m.datumok_szerint).length > 0;
                        return (
                          <td key={m.honap} className={`px-1.5 py-1.5 text-right tabular-nums ${!m.belsos && m.tig_id === null ? "text-text-muted" : ""}`}>
                            {m.allapot === "Kihagyva" ? (
                              <span className="text-text-muted">kihagyva</span>
                            ) : m.netto_osszeg != null ? (
                              formatHuf(m.netto_osszeg).replace(" Ft", "")
                            ) : m.belsos ? (
                              <span className="text-text-muted">–</span>
                            ) : (
                              ""
                            )}
                            {h.length > 0 && <span className="block text-[10.5px] text-text-warning">{h.join(", ")}</span>}
                            {elcsuszott && <span className="block text-[10.5px] text-text-danger">elcsúszott?</span>}
                          </td>
                        );
                      })}
                      <td className="py-1.5 pl-3 text-right font-medium tabular-nums">{formatHuf(s.osszesen)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {sorok.map((s) => (
          <details key={s.employee_id} id={`e${s.employee_id}`} className="rounded-[var(--radius-lg)] border border-border bg-surface-2 p-4">
            <summary className="cursor-pointer text-[14px] font-medium text-text-primary">
              {s.full_name} <span className="ml-2 text-[13px] font-normal text-text-secondary">{formatHuf(s.osszesen)}</span>
              {s.honapok.some((m) => hiany(m).length > 0 || Object.keys(m.datumok_szerint).length > 0) && (
                <span className="ml-2 text-[12px] font-normal text-text-warning">rendezendő</span>
              )}
            </summary>
            <div className="mt-3">
              <RendezesSorok employeeId={s.employee_id} ev={ev} honapok={s.honapok} canEdit={canEdit} />
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
