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
import { ProjektkodTeendoTabla } from "@/components/ProjektkodTeendoTabla";
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
import { projektkodFazisa } from "@/lib/projektkodFazis";

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
      {/* Keretszerződés alatt nincs eseti szerződés-teendő - de azt is ki kell
          írni, MIÉRT nincs, különben az üres hely tűnik hiánynak. */}
      <StatusBadge
        label={
          !pc.szerzodes_kell ? "Keretszerződés alatt" : pc.szerzodes_kesz ? "Szerződés megvan" : "Nincs szerződés"
        }
        tone={!pc.szerzodes_kell || pc.szerzodes_kesz ? "success" : "warning"}
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
  return (
    (!pc.szerzodes_kell || pc.szerzodes_kesz ? 1 : 0) + (pc.tig_kesz ? 1 : 0) + (pc.bevetel_kifizetve ? 1 : 0)
  );
}

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
  // A LEGNAGYOBB projektkód áll elöl: a friss munkák nagyobb sorszámot kapnak,
  // és mindenki ezeken dolgozik - a legrégebbivel kezdeni annyit jelentene,
  // hogy minden megnyitáskor a lista aljára kell görgetni. A `numeric` a
  // sorszámokat számként hasonlítja (HYPE26-9 < HYPE26-10), a fejlécre
  // kattintva természetesen bármelyik oszlop szerint átrendezhető.
  const kodSzerint = (a: ProjectCode, b: ProjectCode) =>
    (b.projektkod ?? "").localeCompare(a.projektkod ?? "", "hu", { numeric: true });
  const sorok = projectCodes.filter((pc) => evheztartozik(pc.projektkod, ev)).sort(kodSzerint);
  // A "Teendők" fülön az számít, HÁNY munkával van dolgunk: minden projektkód,
  // ami még nem jutott el a "kész" fázisig.
  const teendos = projectCodes.filter((pc) => projektkodFazisa(pc) !== "kesz").length;
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

  // A kód eleje mindig ugyanaz az évszámos előtag ("HYPE26-"), csak a négyjegyű
  // sorszám változik - ezt írjuk be előre, hogy ne kelljen minden felvételnél
  // nulláról begépelni. Az évszám a mai napból jön (2027-től magától HYPE27-),
  // és a mező szabadon átírható: egy régebbi évre szóló kód is felvehető.
  const kodElotag = `HYPE${String(new Date().getFullYear()).slice(2)}-`;

  const ujProjektkodUrlap = canCreate ? (
    <QuickCreateForm
      postPath={ENTITY_PATHS.projectCode}
      addLabel="+ Új Project Code hozzáadása"
      fields={[
        {
          name: "projektkod",
          label: "Projektkód",
          required: true,
          defaultValue: kodElotag,
          placeholder: `${kodElotag}0001`,
        },
        // Az ügyfél NEM kötelező: a kódot sokszor előbb foglaljuk le, mint
        // ahogy eldőlne, kinek a munkája - utólag az adatlapon megadható.
        {
          name: "client_id",
          label: "Ügyfél (később is megadható)",
          type: "select",
          options: clients.map((c) => ({ value: c.id, label: c.nev })),
        },
        // Nem naptári dátum, hanem SZÖVEG: egy projektkód alatt több forgatás
        // fut, és a valóságban "2026. május" vagy "két hétvégén" a pontos
        // válasz - a napokat úgyis a projektek hordozzák.
        { name: "datum_megjegyzes", label: "Dátum megjegyzés", placeholder: "Pl. 2026. május" },
      ]}
    />
  ) : null;

  // A TEENDŐK nézet nem szűrt lista, hanem FÁZIS-OSZLOPOK - ugyanaz a tábla,
  // mint az Utókövetésen, csak a másik oldalról: ott a mi fizetéseink útját
  // követi, itt a megrendelő felé menő papírokét és a beérkező pénzét. Egy
  // projektkód pontosan egy oszlopban áll, a legkorábbi hiányzó lépésnél, így
  // balról jobbra haladva az látszik, mi a következő teendő rajta.
  if (ev === "teendok") {
    return (
      <div className="flex flex-1 flex-col">
        <TopBar />
        <div className="flex-1 p-8">
          <Card title={`Teendők (${teendos} projektkód)`}>
            <ProjektkodEvValto aktiv={ev} darabszamok={darabszamok} />
            {/* Ugyanaz a sorrend, mint a listán: a legnagyobb kód elöl. */}
            <ProjektkodTeendoTabla rows={[...projectCodes].sort(kodSzerint)} />
          </Card>
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
