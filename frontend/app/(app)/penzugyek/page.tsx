import { AlertCircle, TrendingDown, TrendingUp, Wallet } from "lucide-react";
import {
  ENTITY_PATHS,
  Expense,
  formatHuf,
  getCurrentUser,
  getExpenses,
  getFieldTypes,
  getFinanceSummary,
  getKiadasSzamlaDarab,
  getMyPagePermissions,
  getProjectCodeOptions,
  getRevenues,
  getUtalasraVaro,
  Revenue,
} from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableBooleanCell } from "@/components/EditableBooleanCell";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { FinanceMonthlyChart, KasszaWidget, OutstandingProjectsTable } from "@/components/finance/FinanceSummaryWidgets";
import { SzamlaCsomagLetoltes } from "@/components/finance/SzamlaCsomagLetoltes";
import { UtalasraVaroSzamlak } from "@/components/finance/UtalasraVaroSzamlak";
import { KiadasProjektkodCella } from "@/components/finance/KiadasProjektkodCella";
import { KimenoSzamlaCella } from "@/components/finance/KimenoSzamlaCella";
import { KiadasSzamlaGomb } from "@/components/finance/KiadasSzamlak";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatCard } from "@/components/StatCard";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import { devizaNyom, PENZNEMEK } from "@/lib/penz";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/penzugyek";

export default async function PenzugyekPage() {
  const [
    expenses,
    revenues,
    summary,
    projectCodes,
    expenseFieldTypes,
    revenueFieldTypes,
    currentUser,
    pagePermissions,
    utalasraVaro,
    szamlaDarab,
  ] = await Promise.all([
    getExpenses(),
    getRevenues(),
    getFinanceSummary(),
    getProjectCodeOptions(),
    getFieldTypes("expense"),
    getFieldTypes("revenue"),
    getCurrentUser(),
    getMyPagePermissions(),
    getUtalasraVaro(),
    getKiadasSzamlaDarab(),
  ]);
  const canCreate = canDoAction(currentUser, pagePermissions, PAGE, "create");
  const canDelete = canDoAction(currentUser, pagePermissions, PAGE, "delete");
  const canEdit = canDoAction(currentUser, pagePermissions, PAGE, "edit");
  // A listát a szerver adja (lásd backend services/entity_registry.py); az itteni
  // érték csak akkor jut szóhoz, ha a mezőleírás nem érkezett meg.
  const fizetesiModOptions = expenseFieldTypes.kifizetes_modja?.options ?? [
    "Készpénz",
    "Átutalás",
    "Bankkártya",
    "Nincs pénzmozgás",
  ];
  // A BEVÉTELNÉL két ÚT van: vagy kézbe kapjuk (kassza), vagy a számlára
  // érkezik - bankkártyát nem fogadunk (lásd backend services/fizetesi_mod.py).
  // A harmadik érték nem út, hanem annak a hiánya: van összeg, de nem mozdult
  // pénz (beszámítás, csere, másik cégen át rendezve).
  const bevetelFizetesiModOptions = revenueFieldTypes.fizetes_modja?.options ?? [
    "Készpénz",
    "Átutalás",
    "Nincs pénzmozgás",
  ];
  // Honnan jött a bevétel: a projektkód és a MUNKA neve. A Revenue maga csak
  // a project_code_id-t hordozza, ezért itt oldjuk fel.
  //
  // Szándékosan nem az ügyfél neve: a régi, Notionból importált kódok
  // többségénél az ügyfél "Ismeretlen ügyfél (Notion import)", vagyis az
  // egész oszlop ugyanazt a semmit írta ki minden soron. A munka nevéből
  // viszont látszik, miről van szó.
  const bevetelForrasa = new Map(
    projectCodes.map((pc) => [
      pc.id,
      { projektkod: pc.projektkod, projektNev: pc.project_nev || null },
    ]),
  );
  // A kiadások Projektkód oszlopának/űrlapjának választéka (lásd
  // KiadasProjektkodCella): kód + a munka neve, kód szerint rendezve.
  const projektkodOpciok = [...projectCodes]
    .sort((a, b) => (b.projektkod ?? "").localeCompare(a.projektkod ?? "", "hu"))
    .map((pc) => ({ id: pc.id, projektkod: pc.projektkod, nev: pc.project_nev || null }));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        {summary && (
          <>
            {/* A nagy számok NETTÓBAN vannak - bevételnél és kiadásnál
                egyaránt (lásd backend services/elszamolas.py). Az ÁFA átfolyó
                tétel: ha az egyik oldalt bruttóban, a másikat nettóban
                néznénk, a "profit" az ÁFA-tartalmak különbségével csúszna el.
                A bruttó ettől még ott van, halványan a szám alatt: az megy ki
                (és jön be) a bankszámlán. */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard
                label="Bevétel (idén, nettó)"
                value={formatHuf(summary.ytd_bevetel)}
                megjegyzes={`Bruttó: ${formatHuf(summary.ytd_bevetel_brutto)}`}
                icon={TrendingUp}
                tone="teal"
              />
              <StatCard
                label="Kiadás (idén, nettó)"
                value={formatHuf(summary.ytd_kiadas)}
                megjegyzes={`Bruttó: ${formatHuf(summary.ytd_kiadas_brutto)}`}
                icon={TrendingDown}
                tone="orange"
              />
              <StatCard
                label="Profit (idén, nettó)"
                value={formatHuf(summary.ytd_profit)}
                megjegyzes="Nettó bevétel mínusz nettó kiadás"
                icon={Wallet}
                tone={summary.ytd_profit >= 0 ? "accent" : "danger"}
              />
              <StatCard
                label={`Kintlévőség (${summary.kintlevo_projektek_szama} projekt, nettó)`}
                value={formatHuf(summary.osszes_kintlevoseg)}
                icon={AlertCircle}
                tone={summary.osszes_kintlevoseg > 0 ? "pink" : "blue"}
              />
            </div>

            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              <Card title="Bevétel / kiadás - utolsó 12 hónap (nettó)">
                <FinanceMonthlyChart trend={summary.havi_trend} />
              </Card>
              {/* MENNYI KÉSZPÉNZ VAN A KASSZÁBAN - a készpénzesnek jelölt
                  bevételek és kiadások különbsége (lásd backend
                  services/fizetesi_mod.py). */}
              <Card title="Készpénz a kasszában">
                <KasszaWidget kassza={summary.kassza} />
              </Card>
              <Card title="Kintlévőségek projektenként">
                <OutstandingProjectsTable projects={summary.kintlevo_projektek} />
              </Card>

            {summary.ytd_kiadas_fizetesi_mod_szerint.length > 0 && (
              <Card title="Kiadás fizetési mód szerint (idén, nettó)">
                <ul className="divide-y divide-border">
                  {summary.ytd_kiadas_fizetesi_mod_szerint.map((row) => (
                    <li key={row.kifizetes_modja ?? "ismeretlen"} className="flex items-center justify-between py-2 text-[13px]">
                      <span className="text-text-secondary">{row.kifizetes_modja ?? "Nincs megadva"}</span>
                      <span className="font-medium text-text-primary">{formatHuf(row.osszeg)}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            </div>
          </>
        )}

        {/* Ami már megérkezett számlaként, de még nem utaltuk el - egy
            listában a három forrásból (kiadás, külsős és belsős TIG), a
            kijelöltek számlái egyben letölthetők. */}
        <Card title={`Utalásra váró számlák (${utalasraVaro.length})`}>
          <UtalasraVaroSzamlak kezdeti={utalasraVaro} />
        </Card>

        {/* Havi számla-csomag a könyvelésnek - egy hónap összes bejövő és
            kimenő számlája egyetlen ZIP-ben. */}
        <Card title="Havi számlák letöltése">
          <SzamlaCsomagLetoltes />
        </Card>

        <Card title={`Kiadások (${expenses.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.expense}
              addLabel="+ Új kiadás hozzáadása"
              // A számla/blokk már felvitelkor csatolható (a felhasználó
              // kérése) - a mentés után a létrejött tételhez töltődik fel.
              fajlFeltoltes={{ entityType: "expense", kategoria: "szamla" }}
              fields={[
                // A `megnevezes` oszlop a felületen "Cégnév" (kinek fizettünk),
                // a "Megnevezés" pedig az új kiadas_leiras: mire ment a pénz
                // (a felhasználó kérése - lásd backend models/finance.Expense).
                { name: "megnevezes", label: "Cégnév", required: true },
                { name: "kiadas_leiras", label: "Megnevezés", placeholder: "Mire ment a kiadás" },
                // KÖTELEZŐ dátum (a felhasználó kérése): a kiadás e nélkül
                // nem köthető hónaphoz - az összesítők és a számla-csomag is
                // ebből dolgozik.
                { name: "kiadas_datuma", label: "Kiadás dátuma", type: "date", required: true },
                { name: "netto", label: "Nettó összeg", type: "number" },
                // "+ÁFA" jelölés + százalék: a bruttót a szerver számolja
                // belőlük (lásd backend routes/finance._afa_brutto).
                {
                  name: "plusz_afa",
                  label: "ÁFA",
                  type: "select",
                  defaultValue: "",
                  options: [
                    { value: "", label: "Nincs ÁFA" },
                    { value: "igen", label: "Plusz ÁFA" },
                  ],
                },
                {
                  name: "afa_szazalek",
                  label: "ÁFA %",
                  type: "number",
                  defaultValue: "27",
                  showIf: { field: "plusz_afa", oneOf: ["igen"] },
                },
                {
                  name: "kifizetes_modja",
                  label: "Fizetési mód",
                  type: "select",
                  // KÖTELEZŐ (a felhasználó kérése): a fizetés típusa nélkül a
                  // kassza és a "Kiadás fizetési mód szerint" összesítő sem
                  // tudja hova sorolni a tételt.
                  required: true,
                  options: fizetesiModOptions.map((m) => ({ value: m, label: m })),
                },
                // Az összeget a választott PÉNZNEMBEN kell beírni; a szerver
                // váltja át forintra az árfolyammal, és a kiadás közé már a
                // forint kerül (lásd backend services/penznem.py). Devizánál az
                // árfolyam kötelező - ha kimarad, beszédes hibát ad.
                {
                  name: "penznem",
                  label: "Pénznem",
                  type: "select",
                  defaultValue: "HUF",
                  options: PENZNEMEK.map((k) => ({ value: k, label: k })),
                },
                {
                  name: "arfolyam",
                  label: "Árfolyam (Ft)",
                  type: "number",
                  required: true,
                  // Csak devizánál kérdezzük: forintnál nincs mit átváltani, és
                  // egy mindig ott álló, üresen hagyott mező azt sugallná,
                  // hogy kellene kitölteni. (Üres pénznem is forintot jelent.)
                  showIf: { field: "penznem", noneOf: ["", "HUF"] },
                },
                // Melyik projektkódra terheljen (a felhasználó kérése) - NEM
                // kötelező: utólag is hozzárendelhető a lista Projektkód
                // oszlopában. A hozzárendelt tétel a projektkód adatlapján is
                // megjelenik (ugyanaz a rekord).
                {
                  name: "project_code_id",
                  label: "Projektkód (ha van)",
                  type: "select",
                  options: projektkodOpciok.map((pc) => ({
                    value: pc.id,
                    label: pc.nev ? `${pc.projektkod} – ${pc.nev}` : pc.projektkod,
                  })),
                },
              ]}
            />
          )}
          <DataTable<Expense>
            // Alap rendezés: a LEGUTÓBB FELVITT tétel legfelül (a felhasználó
            // kérése). Szándékosan id szerint, nem updated_at szerint: egy
            // régi sor szerkesztése ne dobja a lista tetejére.
            rows={[...expenses].sort((a, b) => b.id - a.id)}
            emptyText="Még nincs felvett kiadás - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(e) => `/penzugyek/kiadas/${e.id}`}
            deleteHref={canDelete ? (e) => `${ENTITY_PATHS.expense}/${e.id}` : undefined}
            filterable
            columns={[
              {
                header: "Cégnév",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.expense}/${e.id}`} field="megnevezes" value={e.megnevezes} />
                  ) : (
                    e.megnevezes
                  ),
                sortAccessor: (e) => e.megnevezes,
              },
              {
                header: "Megnevezés",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell
                      patchPath={`${ENTITY_PATHS.expense}/${e.id}`}
                      field="kiadas_leiras"
                      value={e.kiadas_leiras}
                    />
                  ) : (
                    e.kiadas_leiras ?? "–"
                  ),
                sortAccessor: (e) => e.kiadas_leiras,
              },
              { header: "Típus", render: (e) => e.tipus ?? "–", sortAccessor: (e) => e.tipus },
              {
                // Melyik projektkódra terhel a kiadás (a felhasználó kérése):
                // itt látszik, és utólag is hozzárendelhető/átrendelhető - a
                // hozzárendelt tétel a projektkód adatlapján is megjelenik
                // (ugyanaz a rekord).
                header: "Projektkód",
                render: (e) => (
                  <KiadasProjektkodCella
                    expenseId={e.id}
                    projectCodeId={e.project_code_id}
                    opciok={projektkodOpciok}
                    canEdit={canEdit}
                  />
                ),
                sortAccessor: (e) => bevetelForrasa.get(e.project_code_id ?? -1)?.projektkod ?? "",
              },
              {
                // MIKOR történt a kiadás (a felhasználó kérése) - itt, a
                // listában is látszódjon és szerkeszthető legyen.
                header: "Dátum",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell
                      patchPath={`${ENTITY_PATHS.expense}/${e.id}`}
                      field="kiadas_datuma"
                      value={e.kiadas_datuma}
                      type="date"
                    />
                  ) : (
                    e.kiadas_datuma ?? "–"
                  ),
                sortAccessor: (e) => e.kiadas_datuma,
              },
              {
                header: "Nettó",
                align: "right",
                render: (e) => (
                  <>
                    {canEdit ? (
                      <EditableTableCell patchPath={`${ENTITY_PATHS.expense}/${e.id}`} field="netto" value={e.netto} type="number" />
                    ) : (
                      formatHuf(e.netto)
                    )}
                    {/* A tárolt összeg forint - itt írjuk ki, MIBŐL lett. */}
                    {devizaNyom(e) && <span className="mt-0.5 block text-[11.5px] text-text-muted">{devizaNyom(e)}</span>}
                  </>
                ),
                sortAccessor: (e) => e.netto,
              },
              {
                // Szerkeszthető, mert a felvitelkor csak a nettót kérjük be:
                // ha valaki utólag tudja a bruttót (áfás számla), itt írhatja
                // be. Az ELSZÁMOLÁSBA a nettó számít (a projekt költségébe és
                // a Pénzügyek összesítőibe is) - a bruttó a tényleges
                // pénzmozgás (lásd backend services/elszamolas.py).
                header: "Bruttó",
                align: "right",
                render: (e) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.expense}/${e.id}`} field="brutto" value={e.brutto} type="number" />
                  ) : (
                    formatHuf(e.brutto)
                  ),
                sortAccessor: (e) => e.brutto,
              },
              {
                header: "Fizetési mód",
                render: (e) => (
                  <EditableStatusBadge
                    patchPath={`${ENTITY_PATHS.expense}/${e.id}`}
                    field="kifizetes_modja"
                    value={e.kifizetes_modja}
                    options={fizetesiModOptions}
                    placeholder="Nincs megadva"
                  />
                ),
                sortAccessor: (e) => e.kifizetes_modja,
              },
              {
                // Számla-feltöltés felugróban (a felhasználó kérése) - az
                // átvezetett tételek (TIG-kifizetés, autó-költés, KP forgalom)
                // forrásánál feltöltött számlák is itt látszanak.
                header: "Számla",
                align: "right",
                render: (e) => (
                  <KiadasSzamlaGomb
                    expenseId={e.id}
                    canEdit={canEdit}
                    canDelete={canDelete}
                    darab={szamlaDarab[e.id] ?? 0}
                  />
                ),
              },
              // Állapot-oszlop SZÁNDÉKOSAN nincs: a kiadások közé az kerül, ami
              // már ki van fizetve - egy "Kifizetve / Nyitott" jelző itt minden
              // soron ugyanazt mondaná. Ami tényleg utalásra vár, azt a fenti
              // "Utalásra váró számlák" kártya hozza elő (az Expense.kesz mező
              // ettől még megvan, a kiadás saját lapján látszik).
              {
                header: "Beleszámít",
                align: "right",
                render: (e) =>
                  canEdit ? (
                    <EditableBooleanCell
                      patchPath={`${ENTITY_PATHS.expense}/${e.id}`}
                      field="hozzaadas_a_kiadasokhoz"
                      value={e.hozzaadas_a_kiadasokhoz}
                      ureskent
                    />
                  ) : (
                    <StatusBadge
                      label={e.hozzaadas_a_kiadasokhoz === false ? "Nem" : "Igen"}
                      tone={e.hozzaadas_a_kiadasokhoz === false ? "neutral" : "success"}
                    />
                  ),
                sortAccessor: (e) => (e.hozzaadas_a_kiadasokhoz === false ? 0 : 1),
              },
            ]}
          />
        </Card>

        <Card title={`Bevételek (${revenues.length})`}>
          {canCreate && (
            <QuickCreateForm
              postPath={ENTITY_PATHS.revenue}
              addLabel="+ Új bevétel hozzáadása"
              fields={[
                {
                  name: "project_code_id",
                  label: "Project Code",
                  type: "select",
                  required: true,
                  options: projectCodes.map((pc) => ({ value: pc.id, label: pc.projektkod })),
                },
                { name: "netto", label: "Nettó", type: "number" },
                {
                  name: "fizetes_modja",
                  label: "Fizetési mód",
                  type: "select",
                  options: bevetelFizetesiModOptions.map((m) => ({ value: m, label: m })),
                },
                // Lásd a kiadásnál: az összeg a választott pénznemben értendő,
                // a bevételek közé forintban kerül.
                {
                  name: "penznem",
                  label: "Pénznem",
                  type: "select",
                  defaultValue: "HUF",
                  options: PENZNEMEK.map((k) => ({ value: k, label: k })),
                },
                {
                  name: "arfolyam",
                  label: "Árfolyam (Ft)",
                  type: "number",
                  required: true,
                  // Csak devizánál kérdezzük: forintnál nincs mit átváltani, és
                  // egy mindig ott álló, üresen hagyott mező azt sugallná,
                  // hogy kellene kitölteni. (Üres pénznem is forintot jelent.)
                  showIf: { field: "penznem", noneOf: ["", "HUF"] },
                },
              ]}
            />
          )}
          <DataTable<Revenue>
            rows={revenues}
            emptyText="Még nincs felvett bevétel - importáld a Notionból, vagy adj hozzá egyet a fenti gombbal."
            getHref={(r) => `/penzugyek/bevetel/${r.id}`}
            deleteHref={canDelete ? (r) => `${ENTITY_PATHS.revenue}/${r.id}` : undefined}
            filterable
            columns={[
              {
                // Melyik MUNKÁÉRT jött a pénz - a projekt neve, alatta a
                // projektkód. Enélkül a soron nem látszik, honnan jött.
                header: "Honnan",
                render: (r) => {
                  const forras = bevetelForrasa.get(Number(r.project_code_id));
                  if (!forras) return "–";
                  return (
                    <span className="flex flex-col">
                      <span>{forras.projektNev ?? forras.projektkod}</span>
                      {forras.projektNev && <span className="text-[12px] text-text-muted">{forras.projektkod}</span>}
                    </span>
                  );
                },
                sortAccessor: (r) => {
                  const forras = bevetelForrasa.get(Number(r.project_code_id));
                  return forras ? `${forras.projektNev ?? ""} ${forras.projektkod}` : "";
                },
              },
              {
                header: "Forma",
                render: (r) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.revenue}/${r.id}`} field="bevetel_formaja" value={r.bevetel_formaja} />
                  ) : (
                    r.bevetel_formaja ?? "–"
                  ),
                sortAccessor: (r) => r.bevetel_formaja,
              },
              {
                header: "Nettó",
                align: "right",
                render: (r) => (
                  <>
                    {canEdit ? (
                      <EditableTableCell patchPath={`${ENTITY_PATHS.revenue}/${r.id}`} field="netto" value={r.netto} type="number" />
                    ) : (
                      formatHuf(r.netto)
                    )}
                    {devizaNyom(r) && <span className="mt-0.5 block text-[11.5px] text-text-muted">{devizaNyom(r)}</span>}
                  </>
                ),
                sortAccessor: (r) => r.netto,
              },
              {
                header: "Bruttó",
                align: "right",
                render: (r) =>
                  canEdit ? (
                    <EditableTableCell patchPath={`${ENTITY_PATHS.revenue}/${r.id}`} field="brutto" value={r.brutto} type="number" />
                  ) : (
                    formatHuf(r.brutto)
                  ),
                sortAccessor: (r) => r.brutto,
              },
              {
                // HOGYAN jött be a pénz. Ebből számol a kassza egyenlege (lásd
                // backend services/fizetesi_mod.py) - ezért fix a lista, nem
                // szabad szöveg: egy "kp" és egy "Készpénz" külön kategória
                // lenne, és pont annyival lenne hamis az egyenleg.
                header: "Fizetési mód",
                render: (r) => (
                  <EditableStatusBadge
                    patchPath={`${ENTITY_PATHS.revenue}/${r.id}`}
                    field="fizetes_modja"
                    value={r.fizetes_modja}
                    options={bevetelFizetesiModOptions}
                    placeholder="Nincs megadva"
                  />
                ),
                sortAccessor: (r) => r.fizetes_modja,
              },
              {
                // A tárolt összeg mindig forint; ha devizásan vezették fel, az
                // "EUR → HUF" alak mondja meg, mi történt - egy puszta "HUF"
                // elrejtené, hogy a számla euróban szólt.
                header: "Pénznem",
                align: "right",
                render: (r) => (r.eredeti_penznem ? `${r.eredeti_penznem} → HUF` : r.penznem),
                sortAccessor: (r) => r.eredeti_penznem ?? r.penznem,
              },
              // Számla-állapot oszlop SZÁNDÉKOSAN nincs (ahogy a kiadásoknál
              // sem): ami a bevételek közé kerül, az azért kerül oda, mert a
              // pénz rendezve van. A kifizetés jelölése a projektkód "3.
              // Számla" kártyáján történik (határidő → kifizetve), ott jön
              // létre és zárul le ez a sor; a bevétel saját lapján a dátumok
              // továbbra is szerkeszthetők.
              //
              // "Beleszámít" oszlop SZÁNDÉKOSAN nincs a listán: a mező
              // (`beleszamit_a_bevetelekbe`) és a hozzá tartozó indok
              // (`bevetelKihagyasOka`) továbbra is megvan és szerkeszthető a
              // bevétel saját lapján - lásd backend services/elszamolas.py.
              {
                // A kimenő számla PDF-je: maga a számla külső rendszerben
                // készül, ide azért kerül fel, hogy a havi csomagban is benne
                // legyen (lásd SzamlaCsomagLetoltes).
                header: "Számla fájl",
                align: "right",
                render: (r) => (
                  <KimenoSzamlaCella
                    revenueId={r.id}
                    filename={typeof r.szamla_filename === "string" ? r.szamla_filename : null}
                    url={typeof r.szamla_file_url === "string" ? r.szamla_file_url : null}
                    canEdit={canEdit}
                    canDelete={canDelete}
                  />
                ),
                sortAccessor: (r) => (r.szamla_filename ? 1 : 0),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
