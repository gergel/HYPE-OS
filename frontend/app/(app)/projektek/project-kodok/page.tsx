import { Card } from "@/components/Card";
import { DataTable, type Column } from "@/components/DataTable";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import {
  evheztartozik,
  PROJEKTKOD_EVEK,
  ProjektkodEvValto,
  type ProjektkodEv,
} from "@/components/ProjektkodEvValto";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatusBadge } from "@/components/StatusBadge";
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

/** Hol tart ez a projektkód a papírozásban és a pénzben.
 *
 * Három lépés, mindig ugyanabban a sorrendben: szerződés → TIG → kifizetés. A
 * sorrend maga az információ, ezért a jelzők akkor is kint vannak, ha az adott
 * lépés még nem aktuális - így egy pillantásból látszik, hol áll a munka, nem
 * kell megnyitni az adatlapot.
 *
 * Ahol nincs mit papírozni (nem szerződéses munka, vagy papír nélkül
 * elszámolt), ott egyetlen jelző áll: a hiányzó papír nem elmaradás. */
function papirJelzo(pc: ProjectCode) {
  if (!pc.papir_kell) return <StatusBadge label="Nem kell papír" tone="neutral" />;
  return (
    <span className="flex flex-wrap justify-end gap-1">
      <StatusBadge
        label={pc.szerzodes_kesz ? "Szerződés megvan" : "Nincs szerződés"}
        tone={pc.szerzodes_kesz ? "success" : "warning"}
      />
      <StatusBadge label={pc.tig_kesz ? "TIG kész" : "Nincs TIG"} tone={pc.tig_kesz ? "success" : "warning"} />
      <StatusBadge
        label={pc.bevetel_kifizetve ? "Kifizetve" : "Nincs kifizetve"}
        tone={pc.bevetel_kifizetve ? "success" : "warning"}
      />
    </span>
  );
}

/** Meddig jutott: ebből rendeződik a Papírozás oszlop, hogy az elakadt munkák
 * kerüljenek egymás mellé. */
function papirRang(pc: ProjectCode): number {
  if (!pc.papir_kell) return 4;
  return (pc.szerzodes_kesz ? 1 : 0) + (pc.tig_kesz ? 1 : 0) + (pc.bevetel_kifizetve ? 1 : 0);
}

/** A három teendő-blokk. A sorrend a folyamat sorrendje: előbb a szerződés,
 * aztán a TIG, végül a pénz - egy hiányzó szerződést nem lehet TIG-gel
 * pótolni, tehát felül az van, amivel kezdeni kell. */
const TEENDO_BLOKKOK: {
  cim: string;
  leiras: string;
  szures: (pc: ProjectCode) => boolean;
}[] = [
  {
    cim: "Nincs még szerződés",
    leiras: "Papírt igényel, de eseti szerződés még nincs lezárva rá.",
    szures: (pc) => pc.papir_kell && !pc.szerzodes_kesz,
  },
  {
    cim: "Már csak a TIG hiányzik",
    leiras: "A szerződés megvan, a teljesítési igazolás még nem.",
    szures: (pc) => pc.papir_kell && pc.szerzodes_kesz && !pc.tig_kesz,
  },
  {
    cim: "Nincs kifizetve",
    leiras:
      "A papírozás rendben (vagy nem is kell), de a pénz még nem érkezett meg - " +
      "ide kerül az is, ahol egyáltalán nincs bevétel felvezetve.",
    szures: (pc) => (!pc.papir_kell || (pc.szerzodes_kesz && pc.tig_kesz)) && !pc.bevetel_kifizetve,
  },
];

export default async function ProjectKodokPage({
  searchParams,
}: {
  searchParams: Promise<{ ev?: string }>;
}) {
  const params = await searchParams;
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

  // Alapból a FOLYÓ év nézete nyílik meg (azon dolgozunk); ha arra az évre
  // nincs kódrendszerünk, az Összes marad.
  const idei = String(new Date().getFullYear()) as ProjektkodEv;
  const kertEv = params.ev as ProjektkodEv | undefined;
  const ismertNezet =
    !!kertEv && (kertEv === "osszes" || kertEv === "teendok" || PROJEKTKOD_EVEK.some((e) => e.ev === kertEv));
  const ev: ProjektkodEv = ismertNezet
    ? (kertEv as ProjektkodEv)
    : PROJEKTKOD_EVEK.some((e) => e.ev === idei)
      ? idei
      : "osszes";
  const sorok = projectCodes.filter((pc) => evheztartozik(pc.projektkod, ev));
  // A "Teendők" fülön az számít, HÁNY munkával van dolgunk - egy projektkód
  // több blokkban is szerepelhet (pl. nincs TIG ÉS nincs kifizetve), ezért
  // egyszer számoljuk.
  const teendos = projectCodes.filter((pc) => TEENDO_BLOKKOK.some((b) => b.szures(pc))).length;
  const darabszamok = {
    ...Object.fromEntries(
      PROJEKTKOD_EVEK.map((e) => [e.ev, projectCodes.filter((pc) => evheztartozik(pc.projektkod, e.ev)).length]),
    ),
    osszes: projectCodes.length,
    teendok: teendos,
  } as Record<ProjektkodEv, number>;

  // Közös oszlopkészlet: az évek nézete és a Teendők blokkjai ugyanazt a
  // táblát mutatják - két külön definíció előbb-utóbb elcsúszna egymástól.
  const oszlopok: Column<ProjectCode>[] = [
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
                // Kiadás = minden projektkiadás + az utómunka költsége + a
                // projekten dolgozó belsősök napidíja (lásd
                // models/project_code.osszes_koltseg). A belsős rész külön is
                // látszik, mert annak nincs kiadás-sora a Pénzügyekben.
                header: "Kiadás",
                align: "right",
                render: (pc) => (
                  <span
                    title={[
                      `Külsős stáb: ${formatHuf(pc.kulsos_koltseg)}`,
                      `Vágás (utómunka): ${formatHuf(pc.vagas_koltseg)}`,
                      `Belsős munkanapok: ${formatHuf(pc.belsos_munka_koltseg)}`,
                      `Egyéb kiadás: ${formatHuf(pc.egyeb_kiadas)}`,
                    ].join(" · ")}
                  >
                    {formatHuf(pc.osszes_koltseg)}
                    {pc.belsos_munka_koltseg > 0 && (
                      <span className="mt-0.5 block text-[11.5px] text-text-muted">
                        ebből belsős: {formatHuf(pc.belsos_munka_koltseg)}
                      </span>
                    )}
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
      // Hol tart a papírozás és a pénz - ez az oszlop válaszol arra, hogy
      // "melyiken van már szerződés, hol van kész TIG, mit nem fizettek ki",
      // anélkül hogy soronként meg kellene nyitni az adatlapot.
      header: "Papírozás",
      align: "right" as const,
      // Függvényhívás, NEM külön komponens: a szűrő a cellában látszó szövegből
      // dolgozik (lásd DataTable nodeToText), egy komponens-elemből viszont
      // még nem látszik semmi - a jelzők szövege csak így válik szűrhetővé.
      render: (pc: ProjectCode) => papirJelzo(pc),
      sortAccessor: (pc: ProjectCode) => papirRang(pc),
    },
    {
      header: "Státusz",
      align: "right" as const,
      render: (pc: ProjectCode) => (
        <EditableStatusBadge
          patchPath={`${ENTITY_PATHS.projectCode}/${pc.id}`}
          field="esemeny_allapota"
          value={pc.esemeny_allapota}
          options={statusOptions}
        />
      ),
      sortAccessor: (pc: ProjectCode) => pc.esemeny_allapota,
    },
  ];

  const ujProjektkodUrlap = canCreate ? (
    <QuickCreateForm
      postPath={ENTITY_PATHS.projectCode}
      addLabel="+ Új Project Code hozzáadása"
      fields={[
        { name: "projektkod", label: "Projektkód", required: true },
        {
          name: "client_id",
          label: "Ügyfél",
          type: "select",
          required: true,
          options: clients.map((c) => ({ value: c.id, label: c.nev })),
        },
        { name: "datum", label: "Dátum", type: "date" },
      ]}
    />
  ) : null;

  // A TEENDŐK nézet nem egy szűrt lista, hanem három blokk: az elakadás
  // FAJTÁJA a kérdés, nem az, hogy melyik évben történt. Ugyanaz a projektkód
  // két blokkban is szerepelhet (nincs TIG és nincs is kifizetve) - ez nem
  // hiba: mindkét teendő él, és mindkét listáról el kell tűnnie.
  if (ev === "teendok") {
    return (
      <div className="flex flex-1 flex-col">
        <TopBar />
        <div className="flex-1 space-y-6 p-8">
          <Card title={`Teendők (${teendos} projektkód)`}>
            <ProjektkodEvValto aktiv={ev} darabszamok={darabszamok} />
            <p className="text-[12.5px] text-text-muted">
              A projektkódok a folyamat szerint szétszedve. Egy sor több blokkban is állhat, ha több teendő van
              rajta.
            </p>
          </Card>
          {TEENDO_BLOKKOK.map((blokk) => {
            const blokkSorok = projectCodes.filter(blokk.szures);
            return (
              <Card key={blokk.cim} title={`${blokk.cim} (${blokkSorok.length})`}>
                <p className="mb-3 text-[12.5px] text-text-muted">{blokk.leiras}</p>
                <DataTable<ProjectCode>
                  rows={blokkSorok}
                  emptyText="Ebben a fázisban nincs teendő - ez a jó hír."
                  getHref={(pc) => `/projektek/project-kodok/${pc.id}`}
                  deleteHref={canDelete ? (pc) => `${ENTITY_PATHS.projectCode}/${pc.id}` : undefined}
                  filterable
                  columns={oszlopok}
                />
              </Card>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Project Code-ok (${sorok.length})`}>
          <ProjektkodEvValto aktiv={ev} darabszamok={darabszamok} />
          {ujProjektkodUrlap}
          <DataTable<ProjectCode>
            rows={sorok}
            emptyText={
              ev === "osszes"
                ? "Még nincs felvett Project Code - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
                : `Ebben az évben (${ev}) még nincs projektkód - nézd meg az Összes nézetet.`
            }
            getHref={(pc) => `/projektek/project-kodok/${pc.id}`}
            deleteHref={canDelete ? (pc) => `${ENTITY_PATHS.projectCode}/${pc.id}` : undefined}
            filterable
            columns={oszlopok}
          />
        </Card>
      </div>
    </div>
  );
}
