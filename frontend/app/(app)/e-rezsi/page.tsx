import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { GoogleTablazatImport } from "@/components/kotelezettseg/GoogleTablazatImport";
import { ERezsiLista } from "@/components/kotelezettseg/ERezsiLista";
import { getEmployees, getKotelezettsegek, getMyPagePermissions } from "@/lib/api";
import { budapestiMa } from "@/lib/idoszak";
import { canDoPageAction } from "@/lib/permissions";

// SAJÁT jogosultsági kulcs (a felhasználó kérése: az E-Rezsi és az Autók
// külön adható) - a régi /kotelezettsegek grant aliaszon át ugyanígy megnyitja
// (lásd lib/permissions.OLDAL_ALIASZOK). A szerepkör-kapu itt nem érvényes,
// kizárólag a page_permissions dönt (lásd backend routes/kotelezettsegek.py).
const PAGE = "/e-rezsi";

/** E-Rezsi: a cég előfizetései - EGYSZERŰ ADATBÁZISKÉNT.
 *
 * A felhasználó döntése (2026-08-30): nincs forduló-követés és "mikor újul"
 * jelzés - az oldal csak azt mutatja, MENNYIT költünk és MIKOR (havi/éves
 * gyakorisággal), meg az éves szummát. Az adat a Google-táblázat tükre
 * (lásd lenti import), plusz ami kézzel kerül ide.
 *
 * A biztosítások és az autók papírjai (ahol a lejárat-figyelés továbbra is
 * kell) ugyanezen a motoron futnak, külön oldalon (lásd /kotelezettsegek és
 * /autok). */
export default async function ERezsiPage() {
  const [kotelezettsegek, employees, pagePermissions] = await Promise.all([
    getKotelezettsegek({ tipus: "elofizetes" }),
    getEmployees(),
    getMyPagePermissions(),
  ]);

  const emberek = employees
    .map((e) => ({ id: e.id, full_name: e.full_name }))
    .sort((a, b) => a.full_name.localeCompare(b.full_name, "hu"));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-8 p-4 md:p-8">
        {/* A TO-DO-hoz hasonló, tagolt nézet (a felhasználó kérése): összesítő,
            szűrők, és a havi / éves / egyszeri előfizetések külön szekcióban. */}
        <ERezsiLista
          kotelezettsegek={kotelezettsegek}
          emberek={emberek}
          canEdit={canDoPageAction(pagePermissions, PAGE, "edit")}
          canCreate={canDoPageAction(pagePermissions, PAGE, "create")}
          canDelete={canDoPageAction(pagePermissions, PAGE, "delete")}
          ma={budapestiMa()}
        />

        {canDoPageAction(pagePermissions, PAGE, "create") && (
          <Card title="Behozatal Google Táblázatból">
            <GoogleTablazatImport />
          </Card>
        )}
      </div>
    </div>
  );
}
