import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { TopBar } from "@/components/TopBar";
import { KeretszerzodesAddWidget } from "@/components/KeretszerzodesAddWidget";
import { StopClickPropagation } from "@/components/StopClickPropagation";
import {
  ENTITY_PATHS,
  formatDate,
  getContracts,
  getCurrentUser,
  getEmployees,
  getMyPagePermissions,
  type Contract,
} from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/penzugyek";

/** Az állapot nélküli bejegyzések helyben rendezhetők - ezek az értékek
 * kínálódnak fel. Az "Aktív" ugyanaz, amit a kézi felvétel is beír (lásd
 * backend routes/contracts.py create_keretszerzodes). */
const ALLAPOT_ALAPOK = ["Aktív", "Lejárt", "Felmondva"];

type KeretszerzodesRow = Contract & { employee_name: string; megkotott: boolean };

/** Meg van-e KÖTVE a szerződés, vagy csak a bejegyzés van meg?
 *
 * A Notion-import minden munkatárs lapjáról áthozza a cégadatot (cégnév,
 * székhely, adószám), ezért sokaknál keletkezett olyan sor, ami mögött nincs
 * aláírt papír - csak a vállalkozás adatai. Ezek a sorok IS ide tartoznak (a
 * lista mindenkit mutat, akinél van szerződés-bejegyzés), de jelezzük őket:
 * amíg nincs állapotuk, az utókövetés projektenként továbbra is kéri az eseti
 * szerződést (lásd backend models/contract.py megkotott_keretszerzodes). */
function megkotott(c: Contract): boolean {
  return Boolean(c.alairva || c.szerzodes_file_url || c.szerzodes_allapota);
}

/** Keretszerződések: a KÜLSŐS munkatársakhoz tartozó álló megbízási
 * szerződések - ezek NEM egy konkrét projekthez kötöttek
 * (Contract.project_id == null).
 *
 * Mindenki szerepel a listán, akinél van ilyen szerződés-bejegyzés, akkor is,
 * ha a szerződésnek nincs állapota - az állapot hiánya nem azt jelenti, hogy
 * nincs ott szerződés. Csak külsősök: a belsősöknél a havi bérelszámolás és a
 * belsős TIG fedi le ugyanezt. */
export default async function KeretszerzodesekPage() {
  const [contracts, employees, currentUser, pagePermissions] = await Promise.all([
    getContracts(),
    getEmployees(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const employeeById = new Map(employees.map((e) => [e.id, e]));
  const canEdit = canDoAction(currentUser?.role, pagePermissions, PAGE, "edit");

  const rows: KeretszerzodesRow[] = contracts
    .filter((c) => {
      if (c.tipus !== "alvallalkozoi" || c.project_id || !c.employee_id) return false;
      return employeeById.get(c.employee_id)?.tipus === "kulsos";
    })
    .map((c) => ({
      ...c,
      employee_name: employeeById.get(c.employee_id as number)?.full_name ?? `#${c.employee_id}`,
      megkotott: megkotott(c),
    }));

  // Felvenni azt a külsőst lehet, akinél még egyáltalán nincs bejegyzés - a
  // cégadat-only sort a backend előlépteti, nem duplikálja (lásd
  // routes/contracts.py create_keretszerzodes). Belsőst nem ajánlunk.
  const linkedEmployeeIds = new Set(rows.map((r) => r.employee_id));
  const candidates = employees.filter((e) => e.tipus === "kulsos" && !linkedEmployeeIds.has(e.id));
  const allapotNelkul = rows.filter((r) => !r.megkotott).length;
  const allapotOpciok = [
    ...new Set([...ALLAPOT_ALAPOK, ...rows.map((r) => r.szerzodes_allapota).filter((a): a is string => !!a)]),
  ];

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Keretszerződések (${rows.length})`}>
          <KeretszerzodesAddWidget candidates={candidates} />
          {allapotNelkul > 0 && (
            <p className="mb-3 text-[12.5px] text-text-muted">
              {allapotNelkul} bejegyzésnek nincs állapota. Ezek is itt vannak, de amíg nincs kitöltve az állapotuk (vagy
              feltöltve az aláírt szerződés), az utókövetés projektenként eseti szerződést kér tőlük - az Állapot
              oszlopban egy kattintással beállítható.
            </p>
          )}
          <DataTable<KeretszerzodesRow>
            filterable
            rows={rows}
            emptyText="Még nincs felvett keretszerződés."
            getHref={(c) => `/csapat/${c.employee_id}`}
            deleteHref={(c) => `${ENTITY_PATHS.contract}/${c.id}`}
            columns={[
              { header: "Munkatárs", render: (c) => c.employee_name, sortAccessor: (c) => c.employee_name },
              { header: "Cég neve", render: (c) => c.ceg_neve ?? "–", sortAccessor: (c) => c.ceg_neve },
              { header: "Adószám", render: (c) => c.adoszam ?? "–", sortAccessor: (c) => c.adoszam },
              {
                // Az állapot helyben állítható: az importált, cégadat-only
                // sorok így egy kattintással "Aktív"-vá tehetők, és onnantól
                // az utókövetés sem kér tőlük eseti szerződést.
                header: "Állapot",
                render: (c) =>
                  canEdit ? (
                    <EditableStatusBadge
                      patchPath={`${ENTITY_PATHS.contract}/${c.id}`}
                      field="szerzodes_allapota"
                      value={c.szerzodes_allapota ?? null}
                      options={allapotOpciok}
                    />
                  ) : (
                    (c.szerzodes_allapota ?? <span className="text-text-muted">Nincs állapot</span>)
                  ),
                sortAccessor: (c) => c.szerzodes_allapota,
              },
              {
                header: "Keltezés",
                align: "right",
                render: (c) => formatDate(c.keltezes),
                sortAccessor: (c) => c.keltezes,
              },
              {
                // A szerződés saját adatlapja: itt tölthető fel és nézhető meg
                // az aláírt PDF (a sor kattintása a munkatárshoz visz, ezért
                // ez a link megállítja a sor-navigációt).
                header: "Dokumentumok",
                align: "right",
                render: (c) => (
                  <StopClickPropagation>
                    <a href={`/szerzodesek/${c.id}`} className="text-text-accent hover:underline">
                      Fájlok
                    </a>
                  </StopClickPropagation>
                ),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
