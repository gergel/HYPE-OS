import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { AutoKezelo } from "@/components/kotelezettseg/AutoKezelo";
import { getAutok, getEmployees, getKotelezettsegek, getLathatjakAzOldalt, getMyPagePermissions } from "@/lib/api";
import { canDoPageAction } from "@/lib/permissions";
import { formatHuf } from "@/lib/penz";

// Saját jogosultsági kulcs - a szerepkör-kapu itt nem érvényes, kizárólag a
// page_permissions dönt (lásd backend routes/autok.py _MINDEN_SZEREPKOR). Az
// /autok jog a kötelezettség-motort is megnyitja a biztosításokhoz (lásd
// lib/permissions.OLDAL_ALIASZOK).
const PAGE = "/autok";

/** Céges autók: mikor jár le a forgalmi és a biztosítás, és mennyit költünk
 * rájuk.
 *
 * A két dolog két, már meglévő rendszerből jön (lásd backend models/auto.py):
 * a határidők kötelezettségek - tehát ugyanúgy szól a lejáratukról, mint
 * bármelyik biztosításról -, a költések pedig sima kiadások, ezért jelennek
 * meg magától a Pénzügy összesítő kiadásai közt is. */
export default async function AutokPage() {
  const [autok, hataridok, employees, pagePermissions, teendoFelelosIdk] = await Promise.all([
    getAutok(),
    // Az autókhoz kötött határidők - a kötelezettség-szerkesztő ezekkel
    // dolgozik az egyes járművek alatt.
    getKotelezettsegek(),
    getEmployees(),
    getMyPagePermissions(),
    // Teendő csak olyanra osztható, aki hozzáfér ehhez az oldalhoz - a
    // backend is ezt ellenőrzi (routes/autok.py _teendo_felelos_ellenorzese).
    getLathatjakAzOldalt(PAGE),
  ]);

  const autosHataridok = hataridok.filter((k) => k.auto_id != null);
  const lejart = autok.filter((a) => a.hatarido_allapot === "lejart").length;
  const hamarosan = autok.filter((a) => a.hatarido_allapot === "hamarosan").length;
  const osszKoltseg = autok.reduce((sum, a) => sum + a.koltseg_osszesen, 0);

  const emberek = employees
    .map((e) => ({ id: e.id, full_name: e.full_name }))
    .sort((a, b) => a.full_name.localeCompare(b.full_name, "hu"));

  // A teendő-felelős választóba csak az oldalhoz hozzáférők kerülnek.
  const teendoEmberek = emberek.filter((e) => teendoFelelosIdk.includes(e.id));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <Card title={`Autók (${autok.length})`}>
          <p className="mb-4 text-[13px] text-text-secondary">
            {autok.length === 0
              ? "Vedd fel az autókat, majd mindegyikhez a forgalmi és a biztosítás lejáratát – a felelős a lejárat előtt feladatot és értesítést kap."
              : `${lejart > 0 ? `${lejart} autónál lejárt papír · ` : ""}${
                  hamarosan > 0 ? `${hamarosan} autónál hamarosan lejár · ` : ""
                }eddigi költés összesen: ${formatHuf(osszKoltseg)} nettó`}
          </p>
          <AutoKezelo
            autok={autok}
            hataridok={autosHataridok}
            emberek={emberek}
            teendoEmberek={teendoEmberek}
            canEdit={canDoPageAction(pagePermissions, PAGE, "edit")}
            canCreate={canDoPageAction(pagePermissions, PAGE, "create")}
            canDelete={canDoPageAction(pagePermissions, PAGE, "delete")}
          />
        </Card>
      </div>
    </div>
  );
}
