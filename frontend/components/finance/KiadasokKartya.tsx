import {
  ENTITY_PATHS,
  Expense,
  formatHuf,
  getCurrentUser,
  getEmployees,
  getExpenses,
  getFieldTypes,
  getKiadasSzamlaDarab,
  getMyPagePermissions,
  getProjectCodeOptions,
} from "@/lib/api";
import { Card } from "@/components/Card";
import { DataTable } from "@/components/DataTable";
import { EditableBooleanCell } from "@/components/EditableBooleanCell";
import { EditableStatusBadge } from "@/components/EditableStatusBadge";
import { EditableTableCell } from "@/components/EditableTableCell";
import { KiadasProjektkodCella } from "@/components/finance/KiadasProjektkodCella";
import { KiadasSzamlaGomb } from "@/components/finance/KiadasSzamlak";
import { DatumSzuro } from "@/components/finance/DatumSzuro";
import { QuickCreateForm } from "@/components/QuickCreateForm";
import { StatusBadge } from "@/components/StatusBadge";
import { idoszakban } from "@/lib/idoszak";
import { devizaNyom, PENZNEMEK } from "@/lib/penz";
import { canDoAction } from "@/lib/permissions";
import { PENZUGYEK_PAGE, szurtOsszegzes } from "@/components/finance/listaSegedek";

/** A KIADÁSOK listája a felvivő űrlappal és a dátum-szűrővel.
 *
 * Két helyen él (a felhasználó kérése: a gyorsabb elérés miatt külön oldalon
 * is legyen): a Pénzügyek oldalon és a saját /penzugyek/kiadasok oldalán.
 * Ugyanaz a komponens, így a kettő nem tud elcsúszni egymástól. A szűrő az
 * URL `kiadas_tol` / `kiadas_ig` paramétereiből jön (lásd DatumSzuro). */
export async function KiadasokKartya({ tol, ig }: { tol: string; ig: string }) {
  const [expenses, projectCodes, expenseFieldTypes, currentUser, pagePermissions, szamlaDarab, employees] =
    await Promise.all([
      getExpenses(),
      getProjectCodeOptions(),
      getFieldTypes("expense"),
      getCurrentUser(),
      getMyPagePermissions(),
      getKiadasSzamlaDarab(),
      // Az alvállalkozó-választóhoz (a felhasználó kérése: a kiadáshoz itt is
      // hozzá lehessen kötni - vagy újként felvenni - az alvállalkozót).
      getEmployees(),
    ]);
  const PAGE = PENZUGYEK_PAGE;
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
  const projektkodNeve = new Map(projectCodes.map((pc) => [pc.id, pc.projektkod]));
  // A listázott kiadások: a dátum nélküli, még ki nem fizetett (csak a
  // projektkódon élő) tételek nélkül, a dátum-szűrő szerint (fizetés dátuma).
  const listazottKiadasok = expenses
    .filter((e) => e.kesz || e.fizetes_datuma !== null)
    .filter((e) => idoszakban(e.fizetes_datuma, tol, ig));
  // A kiadások Projektkód oszlopának/űrlapjának választéka (lásd
  // KiadasProjektkodCella): kód + a munka neve, kód szerint rendezve.
  const projektkodOpciok = [...projectCodes]
    .sort((a, b) => (b.projektkod ?? "").localeCompare(a.projektkod ?? "", "hu"))
    .map((pc) => ({ id: pc.id, projektkod: pc.projektkod, nev: pc.project_nev || null }));

  return (
    <Card title={`Kiadások (${listazottKiadasok.length})`}>
      <DatumSzuro
        elotag="kiadas"
        tol={tol}
        ig={ig}
        mire="fizetés dátuma"
        osszegzes={szurtOsszegzes(listazottKiadasok)}
      />
      {canCreate && (
        <QuickCreateForm
          postPath={ENTITY_PATHS.expense}
          addLabel="+ Új kiadás hozzáadása"
          // A számla/blokk már felvitelkor csatolható (a felhasználó
          // kérése) - a mentés után a létrejött tételhez töltődik fel.
          fajlFeltoltes={{
            entityType: "expense",
            kategoria: "szamla",
            // "Nincs számla" kapcsoló (a felhasználó kérése).
            nincsKapcsolo: { name: "nincs_szamla" },
          }}
          // A feltöltött szerződésből/számlából az AI előtölti a mezőket
          // (a felhasználó kérése) - lásd backend services/kiadas_kiolvasas.py.
          aiKitoltes={{ endpoint: "/api/v1/expenses/kiolvasas" }}
          fields={[
            // A `megnevezes` oszlop a felületen "Cégnév" (kinek fizettünk),
            // a "Megnevezés" pedig az új kiadas_leiras: mire ment a pénz
            // (a felhasználó kérése - lásd backend models/finance.Expense).
            { name: "megnevezes", label: "Cégnév", required: true },
            { name: "kiadas_leiras", label: "Megnevezés", placeholder: "Mire ment a kiadás" },
            // KÖTELEZŐ dátum (a felhasználó kérése): a kiadás e nélkül
            // nem köthető hónaphoz - az összesítők és a számla-csomag is
            // ebből dolgozik.
            { name: "fizetes_datuma", label: "Fizetés dátuma", type: "date", required: true },
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
                // A számlán szereplő ÁFA konkrét ÖSSZEGE (nem százalék) -
                // pl. vegyes kulcsnál; bruttó = nettó + ez az összeg.
                { value: "egyeni", label: "Egyéni ÁFA összeg" },
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
              name: "egyeni_afa_osszege",
              label: "ÁFA összege",
              type: "number",
              placeholder: "A számlán szereplő ÁFA",
              required: true,
              showIf: { field: "plusz_afa", oneOf: ["egyeni"] },
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
            // BESOROLÁS + ALVÁLLALKOZÓ - ugyanaz a páros, mint a
            // projektkód oldali kiadás-űrlapon: az alvállalkozó
            // kiválasztása automatikusan Külsősre állítja a besorolást
            // (szerződés/TIG csak arról jár), a nem létező név pedig a
            // kereső "hozzáadása újként" sorával vehető fel - az AI-s
            // kitöltés is ezt a mezőt tölti/nyitja (a felhasználó kérése).
            {
              name: "tipus",
              label: "Besorolás",
              type: "select",
              defaultValue: "egyeb",
              options: [
                { value: "egyeb", label: "Egyéb" },
                { value: "kulsos", label: "Külsős" },
              ],
            },
            {
              name: "employee_id",
              label: "Alvállalkozó (ha van)",
              type: "select",
              autoSet: { field: "tipus", value: "kulsos" },
              ujAlvallalkozo: true,
              options: [...employees]
                .sort((a, b) => a.full_name.localeCompare(b.full_name, "hu"))
                .map((e) => ({ value: e.id, label: e.full_name })),
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
        //
        // A DÁTUM NÉLKÜLI, még ki nem fizetett tételek NEM szerepelnek (a
        // felhasználó kérése): azok csak a projektkódjukon élnek, és a
        // Fizetés gomb + fizetés-dátum megadása után kerülnek ide.
        rows={[...listazottKiadasok].sort((a, b) => b.id - a.id)}
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
            sortAccessor: (e) => projektkodNeve.get(e.project_code_id ?? -1) ?? "",
          },
          {
            // A listában a FIZETÉS (kifizetés) dátuma látszik (a felhasználó
            // kérése), nem a kiadás/teljesítés dátuma. A kifizetéskor
            // (utalás felvezetése) töltődik; itt kézzel is javítható.
            header: "Fizetés dátuma",
            render: (e) =>
              canEdit ? (
                <EditableTableCell
                  patchPath={`${ENTITY_PATHS.expense}/${e.id}`}
                  field="fizetes_datuma"
                  value={e.fizetes_datuma}
                  type="date"
                />
              ) : (
                e.fizetes_datuma ?? "–"
              ),
            sortAccessor: (e) => e.fizetes_datuma,
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
            render: (e) =>
              // A felvitelkor bejelölt "nincs számla" (a felhasználó
              // kérése): nem hiányzik, nem is lesz - fájl ettől még
              // utólag feltölthető a gemkapoccsal.
              e.nincs_szamla && !(szamlaDarab[e.id] ?? 0) ? (
                <span className="text-[12px] text-text-muted">Nincs számla</span>
              ) : (
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
  );
}
