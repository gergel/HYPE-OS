import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { Card } from "@/components/Card";
import { KiadasKapcsolatok } from "@/components/finance/KiadasKapcsolatok";
import { KiadasSzamlak } from "@/components/finance/KiadasSzamlak";
import { AdatlapFej, PenzugyiSzekciok, type Jelveny } from "@/components/finance/PenzugyiAdatlap";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getCurrentUser,
  getEmployees,
  getFieldTypes,
  getMyPagePermissions,
  getProjectCodeOptions,
  getRecord,
  getVisibleFields,
} from "@/lib/api";
import { formatHuf } from "@/lib/penz";
import { canDoAction } from "@/lib/permissions";

const TIPUS_CIMKE: Record<string, string> = { belsos: "Belsős", kulsos: "Külsős", extra: "Extra", egyeb: "Egyéb" };

function szam(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default async function ExpenseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const expenseId = Number(id);

  // A projectCode/employee a kiadás mezőitől függ - a mezőleírók nem, ezért
  // azok a getRecord-dal EGYSZERRE indulnak, nem utána.
  const [expense, visibleFields, fieldTypes, currentUser, pagePermissions] = await Promise.all([
    getRecord(ENTITY_PATHS.expense, expenseId),
    getVisibleFields("expense"),
    getFieldTypes("expense"),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  if (!expense) notFound();
  const canEdit = canDoAction(currentUser, pagePermissions, "/penzugyek", "edit");
  const canDelete = canDoAction(currentUser, pagePermissions, "/penzugyek", "delete");

  const [projectCode, employee, projektkodok, emberek] = await Promise.all([
    expense.project_code_id ? getRecord(ENTITY_PATHS.projectCode, Number(expense.project_code_id)) : null,
    expense.employee_id ? getRecord(ENTITY_PATHS.employee, Number(expense.employee_id)) : null,
    // A csere/hozzáadás választéka - csak akkor kell, ha szerkeszthet.
    canEdit ? getProjectCodeOptions() : Promise.resolve([]),
    canEdit ? getEmployees() : Promise.resolve([]),
  ]);

  const tipus = String(expense.tipus ?? "").trim().toLowerCase();
  const brutto = szam(expense.brutto);
  const netto = szam(expense.netto);
  const deviza = expense.eredeti_penznem ? String(expense.eredeti_penznem) : null;
  const vanKulsosAdat = ["tulora_osszege", "tulora_orabere", "tulora_szama", "plusz_napok_ara", "plusz_napok_szama"].some(
    (k) => szam(expense[k]) !== null,
  );

  const jelvenyek: Jelveny[] = [
    expense.kesz ? { label: "Kifizetve", tone: "success" } : { label: "Fizetésre vár", tone: "warning" },
  ];
  if (expense.kifizetes_modja) jelvenyek.push({ label: String(expense.kifizetes_modja), tone: "neutral" });
  if (tipus) jelvenyek.push({ label: TIPUS_CIMKE[tipus] ?? String(expense.tipus), tone: "accent" });
  if (expense.kp_fedezet) jelvenyek.push({ label: "Fedezet", tone: "blue" });
  if (expense.nincs_szamla) jelvenyek.push({ label: "Sosem lesz számla", tone: "danger" });
  if (deviza) jelvenyek.push({ label: `Devizás (${deviza})`, tone: "teal" });


  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        <BackLink href="/penzugyek" label="Pénzügyek" />

        <AdatlapFej
          felirat="Kiadás"
          cim={String(expense.megnevezes ?? `Kiadás #${expense.id}`)}
          osszeg={brutto !== null ? formatHuf(brutto) : netto !== null ? formatHuf(netto) : null}
          osszegAlatt={brutto !== null && netto !== null ? `bruttó · nettó ${formatHuf(netto)}` : brutto !== null ? "bruttó" : netto !== null ? "nettó" : null}
          jelvenyek={jelvenyek}
          // A projektkód és az alvállalkozó lent, a saját kártyáján látszik
          // (ott szerkeszthető és levehető is).
          linkek={[]}
        />

        {/* A projektkód és az alvállalkozó itt adható hozzá, cserélhető és
            vehető le (a felhasználó kérése) - lásd KiadasKapcsolatok. */}
        <Card title="Projektkód és alvállalkozó">
          <KiadasKapcsolatok
            expenseId={expenseId}
            projectCode={
              projectCode
                ? {
                    id: Number(projectCode.id),
                    projektkod: String(projectCode.projektkod ?? ""),
                    nev: projectCode.project_nev ? String(projectCode.project_nev) : null,
                  }
                : null
            }
            employee={employee ? { id: Number(employee.id), nev: String(employee.full_name ?? "") } : null}
            projektkodOpciok={[...projektkodok]
              .sort((a, b) => (b.projektkod ?? "").localeCompare(a.projektkod ?? "", "hu"))
              .map((pc) => ({ value: String(pc.id), label: pc.projektkod, sublabel: pc.project_nev || undefined }))}
            emberOpciok={[...emberek]
              .sort((a, b) => a.full_name.localeCompare(b.full_name, "hu"))
              .map((e) => ({ value: String(e.id), label: e.full_name }))}
            canEdit={canEdit}
          />
        </Card>

        {/* Csak a fontos mezők, szekciókba rendezve (a felhasználó kérése) -
            a Notionből átjött, nem használt mezők a csukott „Régi adatok”
            blokkba kerülnek (lásd PenzugyiAdatlap). */}
        <PenzugyiSzekciok
          record={expense}
          fieldTypes={fieldTypes}
          visibleFields={visibleFields}
          patchPath={`${ENTITY_PATHS.expense}/${expense.id}`}
          readOnly={!canEdit}
          // A kapcsolatok a fejlécben linkként látszanak.
          rejtett={["project_code_id", "employee_id", "alvallalkozo_project_id", "auto_id"]}
          szekciok={[
            {
              key: "alap",
              cim: "Alapadatok",
              mezok: [
                // A kiadásnál a `megnevezes` a felületen "Cégnév" (kinek
                // fizettünk) - lásd backend models/finance.
                { key: "megnevezes", label: "Cégnév" },
                { key: "tipus", label: "Típus" },
                { key: "kiadas_leiras", label: "Leírás" },
                { key: "megjegyzes", label: "Megjegyzés" },
              ],
            },
            {
              key: "osszeg",
              cim: "Összeg",
              mezok: [
                { key: "netto", label: "Nettó" },
                { key: "afa_szazalek", label: "ÁFA %" },
                { key: "egyeni_afa_osszege", label: "Egyéni ÁFA összege" },
                { key: "brutto", label: "Bruttó" },
                { key: "penznem", label: "Pénznem" },
              ],
            },
            {
              key: "deviza",
              cim: "Deviza",
              lathato: Boolean(deviza) || szam(expense.arfolyam) !== null,
              mezok: [
                { key: "eredeti_penznem", label: "Eredeti pénznem" },
                { key: "eredeti_netto", label: "Eredeti nettó" },
                { key: "eredeti_brutto", label: "Eredeti bruttó" },
                { key: "arfolyam", label: "Árfolyam" },
              ],
            },
            {
              key: "fizetes",
              cim: "Fizetés",
              mezok: [
                { key: "kesz", label: "Kifizetve" },
                { key: "kifizetes_modja", label: "Fizetési mód" },
                { key: "fizetes_datuma", label: "Fizetés dátuma" },
                { key: "fizetes_hatarideje", label: "Fizetési határidő" },
              ],
            },
            {
              key: "szamla",
              cim: "Számla",
              mezok: [
                { key: "nincs_szamla", label: "Sosem lesz számlája" },
                { key: "kp_fedezet", label: "Fedezet (pénz nem jött ki)" },
              ],
              // A kiadás számlái: közvetlen feltöltés, és - átvezetett
              // tételnél - a forrásnál (TIG, autó, KP forgalom) feltöltött
              // számlák is, hogy ne kelljen kétszer feltölteni.
              extra: <KiadasSzamlak expenseId={expenseId} canEdit={canEdit} canDelete={canDelete} />,
            },
            {
              key: "kulsos",
              cim: "Külsős tételek (túlóra, plusz napok)",
              lathato: tipus === "kulsos" || vanKulsosAdat,
              mezok: [
                { key: "tulora_szama", label: "Túlóra (óra)" },
                { key: "tulora_orabere", label: "Túlóra órabér" },
                { key: "tulora_osszege", label: "Túlóra összege" },
                { key: "plusz_napok_szama", label: "Plusz napok száma" },
                { key: "plusz_napok_ara", label: "Plusz nap ára" },
              ],
            },
          ]}
        />
      </div>
    </div>
  );
}
