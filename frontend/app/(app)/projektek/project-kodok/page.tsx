import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  formatHuf,
  getClients,
  getCurrentUser,
  getFieldTypes,
  getMyPagePermissions,
  getProjectCodes,
  ProjectCode,
} from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/projektek/project-kodok";

export default async function ProjectKodokPage() {
  const [projectCodes, clients, fieldTypes, currentUser, pagePermissions] = await Promise.all([
    getProjectCodes(),
    getClients(),
    getFieldTypes("projectCode"),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  const statusOptions = fieldTypes.esemeny_allapota?.options ?? [];
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Project Code-ok (${projectCodes.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.projectCode}
              addLabel="+ Új Project Code hozzáadása"
              fields={[
                { name: "projektkod", label: "Projektkód", required: true },
                { name: "client_id", label: "Ügyfél", type: "select", required: true, options: clients.map((c) => ({ value: c.id, label: c.nev })) },
                { name: "datum", label: "Dátum", type: "date" },
              ]}
            />
          )}
          <DataTable<ProjectCode>
            rows={projectCodes}
            emptyText="Még nincs felvett Project Code - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(pc) => `/projektek/project-kodok/${pc.id}`}
            deleteHref={canDelete ? (pc) => `${ENTITY_PATHS.projectCode}/${pc.id}` : undefined}
            filterable
            columns={[
              {
                header: "Projektkód",
                render: (pc) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`} field="projektkod" value={pc.projektkod} />
                  ) : (
                    pc.projektkod
                  ),
                sortAccessor: (pc) => pc.projektkod,
              },
              {
                // Az ügyfél helyén a projekt NEVE áll: a listán a legtöbb sor
                // ugyanazt az "Ismeretlen ügyfél (Notion import)" nevet vitte,
                // tehát az oszlop egy fél képernyőt foglalt anélkül, hogy bármit
                // megkülönböztetett volna. Az ügyfél az adatlapon ott van.
                header: "Projekt neve",
                render: (pc) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`} field="project_nev" value={pc.project_nev} />
                  ) : (
                    (pc.project_nev ?? "–")
                  ),
                sortAccessor: (pc) => pc.project_nev,
              },
              {
                header: "Helyszín",
                render: (pc) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`} field="helyszin" value={pc.helyszin} />
                  ) : (
                    (pc.helyszin ?? "–")
                  ),
                sortAccessor: (pc) => pc.helyszin,
              },
              {
                // Nem a naptári dátum, hanem a hozzá tartozó MEGJEGYZÉS
                // ("2 nap", "csúszik", "több hétvégén") - a projektkód alatt
                // amúgy is több forgatás fut, egyetlen dátum úgysem mondaná meg,
                // mikor volt a munka. A pontos dátum az adatlapon van.
                header: "Dátum megjegyzés",
                render: (pc) =>
                  canEdit ? (
                    <EditableTableCell
                      patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`}
                      field="datum_megjegyzes"
                      value={pc.datum_megjegyzes}
                    />
                  ) : (
                    (pc.datum_megjegyzes ?? "–")
                  ),
                sortAccessor: (pc) => pc.datum_megjegyzes,
              },
              // A három pénz-oszlop SZÁMÍTOTT, ezért nem szerkeszthető: a
              // bevétel a bevétel-sorok, a kiadás a projektkiadások és az
              // utómunka összege (lásd models/project_code.py). Itt átírni őket
              // annyit tenne, hogy a lista mást mond, mint a mögötte álló
              // tételek - a számot a tételeknél kell javítani.
              {
                header: "Bevétel",
                align: "right",
                render: (pc) => <span title="A bevétel-sorok összege - a Pénzügyeknél módosítható">{formatHuf(pc.bevetel)}</span>,
                sortAccessor: (pc) => pc.bevetel,
              },
              {
                // Kiadás = minden projektkiadás + az utómunka költsége, ugyanaz,
                // amit az adatlap "Összes költség (kiadások + utómunka)" néven
                // mutat (lásd models/project_code.osszes_koltseg).
                header: "Kiadás",
                align: "right",
                render: (pc) => (
                  <span title="A projektkiadások és az utómunka költsége - a tételeknél módosítható">
                    {formatHuf(pc.osszes_koltseg)}
                  </span>
                ),
                sortAccessor: (pc) => pc.osszes_koltseg,
              },
              {
                header: "Profit",
                align: "right",
                render: (pc) => (
                  <span
                    title="Bevétel mínusz kiadás - számított érték"
                    className={pc.becsult_profit < 0 ? "text-text-danger" : undefined}
                  >
                    {formatHuf(pc.becsult_profit)}
                  </span>
                ),
                sortAccessor: (pc) => pc.becsult_profit,
              },
              {
                header: "Státusz",
                align: "right",
                render: (pc) => (
                  <EditableStatusBadge
                    patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`}
                    field="esemeny_allapota"
                    value={pc.esemeny_allapota}
                    options={statusOptions}
                  />
                ),
                sortAccessor: (pc) => pc.esemeny_allapota,
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
