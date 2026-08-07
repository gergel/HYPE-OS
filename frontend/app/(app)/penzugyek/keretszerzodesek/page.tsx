import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { KeretszerzodesErvenyesseg } from "@/components/finance/KeretszerzodesErvenyesseg";
import { KeretszerzodesKuldes } from "@/components/finance/KeretszerzodesKuldes";
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
  getVallalkozasok,
  type Contract,
} from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/penzugyek";

/** Az állapot nélküli bejegyzések helyben rendezhetők - ezek az értékek
 * kínálódnak fel. Az "Aktív" ugyanaz, amit a kézi felvétel is beír (lásd
 * backend routes/contracts.py create_keretszerzodes). */
const ALLAPOT_ALAPOK = ["Aktív", "Lejárt", "Felmondva"];

type KeretszerzodesRow = Contract & {
  /** Kivel kötöttük: a külsős munkatárs neve, vagy - ha a szerződés CÉGGEL
   * szól - a cég neve (lásd backend models/vallalkozas.py). */
  employee_name: string;
  /** Cég nevére szóló keretszerződésnél a hozzá tartozó emberek. */
  ceg_tagjai: string[];
};

/** Keretszerződések: a KÜLSŐS munkatársakhoz tartozó ÁLLÓ keretszerződések -
 * azok, akik a Notion "Alvállakozó keretszerződés (külsős)" táblájában
 * szerepelnek (a jelölést az import és a kézi felvétel adja, lásd backend
 * models/contract.py Contract.keretszerzodes).
 *
 * Ami nem ilyen, az eseti megbízási szerződés - az a munkatárs saját
 * adatlapján, az "Eseti megbízási szerződések" szekcióban van. Csak külsősök:
 * a belsősöknél a havi bérelszámolás és a belsős TIG fedi le ugyanezt. */
export default async function KeretszerzodesekPage() {
  const [contracts, employees, vallalkozasok, currentUser, pagePermissions] = await Promise.all([
    getContracts(),
    getEmployees(),
    getVallalkozasok(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const vallalkozasById = new Map(vallalkozasok.map((v) => [v.id, v]));
  const employeeById = new Map(employees.map((e) => [e.id, e]));
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");

  // Emberrel ÉS céggel is köthetünk keretszerződést: az embereket küldő
  // vállalkozás szerződése az összes tőle jövő embert fedi (lásd backend
  // services/szamlazo.py).
  const rows: KeretszerzodesRow[] = contracts
    .filter((c) => {
      if (c.tipus !== "alvallalkozoi" || c.project_id || !c.keretszerzodes) return false;
      if (c.vallalkozas_id) return vallalkozasById.has(c.vallalkozas_id);
      if (!c.employee_id) return false;
      return employeeById.get(c.employee_id)?.tipus === "kulsos";
    })
    .map((c) => {
      const ceg = c.vallalkozas_id ? vallalkozasById.get(c.vallalkozas_id) : undefined;
      return {
        ...c,
        employee_name: ceg
          ? ceg.nev
          : (employeeById.get(c.employee_id as number)?.full_name ?? `#${c.employee_id}`),
        ceg_tagjai: ceg ? ceg.tagok.map((t) => t.full_name) : [],
      };
    });

  // Felvenni azt a külsőst lehet, akinek még nincs keretszerződése. Akinek van
  // eseti megbízási szerződése, az is felvehető: a kettő külön sor, a backend
  // nem írja felül az esetit (lásd routes/contracts.py create_keretszerzodes).
  const linkedEmployeeIds = new Set(rows.map((r) => r.employee_id));
  const candidates = employees.filter((e) => e.tipus === "kulsos" && !linkedEmployeeIds.has(e.id));
  // Cég is felvehető: az embereket küldő vállalkozás keretszerződése az összes
  // tőle jövő embert fedi (lásd backend services/szamlazo.py).
  const linkedCegIds = new Set(rows.map((r) => r.vallalkozas_id));
  const cegJeloltek = vallalkozasok
    .filter((v) => v.aktiv && !linkedCegIds.has(v.id))
    .map((v) => ({ id: v.id, nev: v.nev }));
  const allapotOpciok = [
    ...new Set([...ALLAPOT_ALAPOK, ...rows.map((r) => r.szerzodes_allapota).filter((a): a is string => !!a)]),
  ];

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Keretszerződések (${rows.length})`}>
          <KeretszerzodesAddWidget candidates={candidates} cegek={cegJeloltek} />
          <p className="mb-3 text-[12.5px] text-text-muted">
            Csak az álló keretszerződések – emberrel vagy{" "}
            <a href="/penzugyek/vallalkozasok" className="text-text-accent hover:underline">
              céggel
            </a>{" "}
            kötve. Az eseti megbízási szerződések a munkatárs adatlapján, a &quot;Szerződések&quot; fülön vannak.
          </p>
          <DataTable<KeretszerzodesRow>
            filterable
            rows={rows}
            emptyText="Még nincs felvett keretszerződés."
            getHref={(c) => (c.vallalkozas_id ? "/penzugyek/vallalkozasok" : `/csapat/${c.employee_id}`)}
            deleteHref={(c) => `${ENTITY_PATHS.contract}/${c.id}`}
            columns={[
              {
                header: "Kivel",
                render: (c) => (
                  <span>
                    {c.employee_name}
                    {/* Céges keretszerződésnél az fontos, kiket fed le. */}
                    {c.vallalkozas_id != null && (
                      <span className="block text-[11px] text-text-muted">
                        Cég{c.ceg_tagjai.length > 0 ? ` · ${c.ceg_tagjai.join(", ")}` : ""}
                      </span>
                    )}
                  </span>
                ),
                sortAccessor: (c) => c.employee_name,
              },
              { header: "Cég neve", render: (c) => c.ceg_neve ?? "–", sortAccessor: (c) => c.ceg_neve },
              { header: "Adószám", render: (c) => c.adoszam ?? "–", sortAccessor: (c) => c.adoszam },
              {
                // Az állapot helyben állítható (aktív / lejárt / felmondva),
                // hogy ne kelljen érte megnyitni a szerződés adatlapját.
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
                // Mikor élt a keretszerződés: a kapcsoló és az időszakok.
                // Csak az számít keretszerződésesnek egy projekten, akinek a
                // FORGATÁS NAPJÁN élt a szerződése.
                header: "Érvényesség",
                render: (c) => (
                  <StopClickPropagation>
                    <KeretszerzodesErvenyesseg
                      contractId={c.id}
                      aktiv={c.aktiv}
                      idoszakok={c.idoszakok ?? []}
                      canEdit={canEdit}
                    />
                  </StopClickPropagation>
                ),
                sortAccessor: (c) => (c.aktiv ? "1" : "0"),
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
                    <span className="flex flex-col items-end gap-1">
                      <a href={`/szerzodesek/${c.id}`} className="text-text-accent hover:underline">
                        Fájlok
                      </a>
                      {/* Új kiküldés: akkor is, ha már van szerződése - pl. a
                          régi lejárt (lásd backend routes/contracts.py
                          send_keretszerzodes). */}
                      {canCreate && <KeretszerzodesKuldes contractId={c.id} cegNeve={c.ceg_neve} />}
                    </span>
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
