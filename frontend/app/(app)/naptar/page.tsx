import { NaptarDiszpoContent } from "@/components/NaptarDiszpoContent";
import { TopBar } from "@/components/TopBar";
import { getCurrentUser, getMyPagePermissions, getProjectCodeOptions, getProjects } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/naptar";

/** A Naptár/Diszpó oldal a MEGLÉVŐ, ténylegesen működő diszpó-küldés
 * (backend/app/services/dispo.py, POST /api/v1/projects/{id}/diszpo/*)
 * köré épül, nem a Callsheet/TimelineEvent táblák köré - azok ugyanis
 * jelenleg üresek és semmilyen kódút nem tölti fel őket (a Callsheetet a
 * Notion import is explicit módon kihagyta, a diszpó-küldés minden
 * állapotát közvetlenül a Project rekordon tárolja). Nincs kétlépcsős
 * (INITIAL_BATCH + háttér-betöltés) lapozás, mint a Projektek oldalon -
 * ez az oldal áttekintő/triázs jellegű, nem egy teljes admin adatlista,
 * ezért egyszerűbb, ha a kliens-oldali állapot mindig pontosan a szerver-
 * oldali listát tükrözi (lásd NaptarDiszpoContent - egy diszpó-küldés
 * utáni router.refresh()-nek azonnal látszania kell az állapot-jelzőkön). */
export default async function NaptarPage() {
  const [projects, projectCodes, currentUser, pagePermissions] = await Promise.all([
    getProjects(),
    getProjectCodeOptions(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <NaptarDiszpoContent
          projects={projects}
          projectCodes={projectCodes}
          canSend={canDoAction(currentUser, pagePermissions, PAGE, "edit")}
        />
      </div>
    </div>
  );
}
