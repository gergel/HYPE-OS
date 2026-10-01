import { notFound } from "next/navigation";
import { BackLink } from "@/components/BackLink";
import { KimenoSzamlaCella } from "@/components/finance/KimenoSzamlaCella";
import { AdatlapFej, PenzugyiSzekciok, type Jelveny } from "@/components/finance/PenzugyiAdatlap";
import { TopBar } from "@/components/TopBar";
import {
  ENTITY_PATHS,
  getCurrentUser,
  getFieldTypes,
  getMyPagePermissions,
  getRecord,
  getVisibleFields,
} from "@/lib/api";
import { formatHuf } from "@/lib/penz";
import { canDoAction } from "@/lib/permissions";

function szam(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default async function RevenueDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const revenueId = Number(id);

  // A projectCode a bevétel mezőjétől függ - a mezőleírók nem, ezért azok a
  // getRecord-dal EGYSZERRE indulnak, nem utána.
  const [revenue, visibleFields, fieldTypes, currentUser, pagePermissions] = await Promise.all([
    getRecord(ENTITY_PATHS.revenue, revenueId),
    getVisibleFields("revenue"),
    getFieldTypes("revenue"),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);
  if (!revenue) notFound();
  const canEdit = canDoAction(currentUser, pagePermissions, "/penzugyek", "edit");
  const canDelete = canDoAction(currentUser, pagePermissions, "/penzugyek", "delete");

  const projectCode = revenue.project_code_id ? await getRecord(ENTITY_PATHS.projectCode, Number(revenue.project_code_id)) : null;
  // Honnan jött a bevétel: a projektkód mögötti ügyfél.
  const ugyfel = projectCode?.client_id
    ? await getRecord(ENTITY_PATHS.client, Number(projectCode.client_id))
    : null;

  const brutto = szam(revenue.brutto);
  const netto = szam(revenue.netto);
  const deviza = revenue.eredeti_penznem ? String(revenue.eredeti_penznem) : null;

  const jelvenyek: Jelveny[] = [
    revenue.fizetes_datuma
      ? { label: "Kifizetve", tone: "success" }
      : revenue.szamla_kiallitva_datuma
        ? { label: "Számla kiállítva, fizetésre vár", tone: "warning" }
        : { label: "Nincs kiállítva", tone: "neutral" },
  ];
  if (revenue.fizetes_modja) jelvenyek.push({ label: String(revenue.fizetes_modja), tone: "neutral" });
  if (revenue.bevetel_formaja) jelvenyek.push({ label: String(revenue.bevetel_formaja), tone: "accent" });
  // NULL = beleszámít (lásd backend models/finance), csak a kifejezett hamis jelez.
  if (revenue.beleszamit_a_bevetelekbe === false) jelvenyek.push({ label: "Nem számít az éves bevételbe", tone: "orange" });
  if (deviza) jelvenyek.push({ label: `Devizás (${deviza})`, tone: "teal" });

  const linkek = [
    ...(ugyfel ? [{ href: `/ugyfelek/${ugyfel.id}`, label: `Ügyfél: ${String(ugyfel.nev)}` }] : []),
    ...(projectCode ? [{ href: `/projektek/project-kodok/${projectCode.id}`, label: `Project Code: ${String(projectCode.projektkod)}` }] : []),
  ];

  const cim: string =
    (revenue.nev ? String(revenue.nev) : "") ||
    (projectCode ? `${String(projectCode.projektkod)} bevétel` : String(revenue.bevetel_formaja ?? `Bevétel #${revenue.id}`));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        <BackLink href="/penzugyek" label="Pénzügyek" />

        <AdatlapFej
          felirat="Bevétel"
          cim={cim}
          osszeg={brutto !== null ? formatHuf(brutto) : netto !== null ? formatHuf(netto) : null}
          osszegAlatt={brutto !== null && netto !== null ? `bruttó · nettó ${formatHuf(netto)}` : brutto !== null ? "bruttó" : netto !== null ? "nettó" : null}
          jelvenyek={jelvenyek}
          linkek={linkek}
        />

        {/* Csak a fontos mezők, szekciókba rendezve (a felhasználó kérése) -
            a Notionből átjött, nem használt mezők a csukott „Régi adatok”
            blokkba kerülnek (lásd PenzugyiAdatlap). */}
        <PenzugyiSzekciok
          // NULL = beleszámít: a jelölőnégyzet is így mutassa (különben
          // üresen állna egy valójában beszámító sornál).
          record={{ ...revenue, beleszamit_a_bevetelekbe: revenue.beleszamit_a_bevetelekbe ?? true }}
          fieldTypes={fieldTypes}
          visibleFields={visibleFields}
          patchPath={`${ENTITY_PATHS.revenue}/${revenue.id}`}
          readOnly={!canEdit}
          // A projektkód a fejlécben link, a számlafájl a Számla szekcióban.
          rejtett={["project_code_id", "szamla_filename", "szamla_storage_key", "szamla_file_url"]}
          szekciok={[
            {
              key: "alap",
              cim: "Alapadatok",
              mezok: [
                { key: "nev", label: "Megnevezés" },
                { key: "bevetel_formaja", label: "Bevétel formája" },
                { key: "beleszamit_a_bevetelekbe", label: "Beleszámít az éves bevételbe" },
                { key: "megjegyzes", label: "Megjegyzés" },
              ],
            },
            {
              key: "osszeg",
              cim: "Összeg",
              mezok: [
                { key: "netto", label: "Nettó" },
                { key: "plusz_afa", label: "+ÁFA" },
                { key: "brutto", label: "Bruttó" },
                { key: "penznem", label: "Pénznem" },
              ],
            },
            {
              key: "deviza",
              cim: "Deviza",
              lathato: Boolean(deviza) || szam(revenue.arfolyam) !== null,
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
                { key: "fizetes_modja", label: "Fizetési mód" },
                { key: "fizetes_hatarideje", label: "Fizetési határidő" },
                { key: "fizetes_datuma", label: "Fizetés dátuma" },
              ],
            },
            {
              key: "szamla",
              cim: "Számla",
              mezok: [{ key: "szamla_kiallitva_datuma", label: "Számla kiállítva" }],
              extra: (
                <div className="space-y-1.5">
                  <p className="t-label">Kimenő számla (PDF)</p>
                  <KimenoSzamlaCella
                    revenueId={revenueId}
                    filename={revenue.szamla_filename ? String(revenue.szamla_filename) : null}
                    url={revenue.szamla_file_url ? String(revenue.szamla_file_url) : null}
                    canEdit={canEdit}
                    canDelete={canDelete}
                    balra
                  />
                </div>
              ),
            },
          ]}
        />
      </div>
    </div>
  );
}
