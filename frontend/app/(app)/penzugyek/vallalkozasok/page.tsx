import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { VallalkozasKezelo } from "@/components/finance/VallalkozasKezelo";
import { getCurrentUser, getEmployees, getMyPagePermissions, getVallalkozasok } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/penzugyek";

/** Számlázó cégek: azok a vállalkozások, amik EMBEREKET küldenek a
 * forgatásokra, és a munkájukról ők állítják ki a számlát.
 *
 * A tőlük jövő emberekkel magukkal nincs szerződésünk - a céggel van. Ha a
 * cégnek van élő keretszerződése, az általa küldött emberektől nem kérünk
 * eseti szerződést azokon a projekteken, ahol őt jelöltük meg számlázó félként
 * (lásd backend routes/vallalkozasok.py és services/szamlazo.py).
 *
 * Az itteni tagság javaslat: a tényleges beállítás projektenként történik, a
 * projekt (vagy az Utókövetés) oldal "Ki számláz kiért" szekciójában. */
export default async function VallalkozasokPage() {
  const [vallalkozasok, employees, currentUser, pagePermissions] = await Promise.all([
    getVallalkozasok(),
    getEmployees(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);

  const elo = vallalkozasok.filter((v) => v.van_ervenyes_keretszerzodes).length;
  // Csak külsősöket ajánlunk fel: a belsősök havi bérezésűek, náluk nem
  // kérdés, ki számláz.
  const emberek = employees
    .filter((e) => e.tipus !== "belsos")
    .map((e) => ({ id: e.id, full_name: e.full_name }))
    .sort((a, b) => a.full_name.localeCompare(b.full_name, "hu"));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Számlázó cégek (${vallalkozasok.length})`}>
          <p className="mb-3 text-[12.5px] text-text-muted">
            {vallalkozasok.length === 0
              ? "Még nincs felvéve cég."
              : `${elo} cégnek van élő keretszerződése. A többinél a hozzájuk tartozó embereknél eseti szerződés kell.`}{" "}
            A cégek keretszerződése a{" "}
            <a href="/penzugyek/keretszerzodesek" className="text-text-accent hover:underline">
              Keretszerződések
            </a>{" "}
            fülön is látszik.
          </p>
          <VallalkozasKezelo
            vallalkozasok={vallalkozasok}
            emberek={emberek}
            canEdit={canDoAction(currentUser, pagePermissions, PAGE, "edit")}
            canCreate={canDoAction(currentUser, pagePermissions, PAGE, "create")}
            canDelete={canDoAction(currentUser, pagePermissions, PAGE, "delete")}
          />
        </Card>
      </div>
    </div>
  );
}
