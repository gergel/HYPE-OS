import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { EszkozkivitelekContent } from "@/components/EszkozkivitelekContent";
import { getEszkozKivitelek, getMyPagePermissions, getProjects } from "@/lib/api";
import { canDoPageAction } from "@/lib/permissions";

const PAGE = "/eszkozkivitelek";

/** Eszközkivitelek KEZELŐ oldala (a felhasználó kérése): itt látszik minden
 * kivitel - ki mit vitt el egy forgatásra és mit hozott vissza, kiemelve a
 * HIÁNYT (ami nem jött vissza). Itt generálható a forgatásonkénti 6 jegyű
 * kód is, amivel a stáb a bejelentkezés nélküli /eszkozkivitel oldalon
 * belép. A diszpó-kiküldésbe egyelőre szándékosan nincs bekötve. */
export default async function EszkozkivitelekPage() {
  const [kivitelek, projektek, pagePermissions] = await Promise.all([
    getEszkozKivitelek(),
    getProjects(20000),
    getMyPagePermissions(),
  ]);

  // A kód-generátor projekt-választójának elég a friss időszak: a mai naphoz
  // képest -30..+90 nap forgatásai (a kód úgyis a forgatás vége után 48
  // órával lejár, régi forgatáshoz nincs értelme kódot adni).
  const ma = new Date();
  const tol = new Date(ma.getTime() - 30 * 86400000).toISOString().slice(0, 10);
  const ig = new Date(ma.getTime() + 90 * 86400000).toISOString().slice(0, 10);
  const valaszthatoProjektek = projektek
    .filter((p) => p.forgatas_datuma && p.forgatas_datuma >= tol && p.forgatas_datuma <= ig)
    .map((p) => ({
      id: p.id,
      nev: p.nev ?? `#${p.id}`,
      projektkod: p.projektkod_szoveg ?? null,
      datum: p.forgatas_datuma,
    }));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <Card title={`Eszközkivitelek – ${kivitelek.length} kivitel`}>
          <EszkozkivitelekContent
            kivitelek={kivitelek}
            projektek={valaszthatoProjektek}
            canCreate={canDoPageAction(pagePermissions, PAGE, "create")}
            canDelete={canDoPageAction(pagePermissions, PAGE, "delete")}
          />
        </Card>
      </div>
    </div>
  );
}
