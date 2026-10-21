import { Card } from "@/components/Card";
import { KeretszerzodesKezelo } from "@/components/megrendeloi/KeretszerzodesKezelo";
import { TopBar } from "@/components/TopBar";
import { getCurrentUser, getMegrendeloiKeretek, getMyPagePermissions } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

// SAJÁT jogosultság (a felhasználó kérése) - lásd backend
// routes/megrendeloi_keretszerzodesek.py PAGE.
const PAGE = "/projektek/megrendeloi-keretszerzodesek";

/** Megrendelői keretszerződések: akikkel KERETBEN dolgozunk.
 *
 * Az adat a Notion "Keretszerződés" adatbázisából jön (lásd backend
 * notion_import/importers.import_contracts) - itt lehet újat készíteni,
 * kiküldeni, és a saját vagy aláírt példányt feltölteni.
 *
 * Az ÉLŐ keretszerződés kiváltja az eseti szerződést, a teljesítési igazolást
 * viszont NEM (lásd backend services/megrendeloi_papir.py). */
export default async function MegrendeloiKeretszerzodesekPage() {
  const [keretek, currentUser, pagePermissions] = await Promise.all([
    getMegrendeloiKeretek(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);

  const elok = keretek.filter((k) => k.ervenyes).length;
  const alairtak = keretek.filter((k) => k.alairva).length;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <Card title={`Megrendelői keretszerződések (${keretek.length})`}>
          <p className="mb-3 text-[12.5px] text-text-muted">
            {elok} keretszerződés él ma, {alairtak} van meg aláírva. Ahol él a keret, ott a projektkódhoz nem kell
            eseti szerződés – teljesítési igazolás viszont igen, mert az egy konkrét munka elkészültéről szól.
          </p>
          <KeretszerzodesKezelo
            keretek={keretek}
            canCreate={canDoAction(currentUser, pagePermissions, PAGE, "create")}
            canEdit={canDoAction(currentUser, pagePermissions, PAGE, "edit")}
            canDelete={canDoAction(currentUser, pagePermissions, PAGE, "delete")}
          />
        </Card>
      </div>
    </div>
  );
}
