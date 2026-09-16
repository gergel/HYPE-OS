import { TopBar } from "@/components/TopBar";
import { MunkafelajanlasContent } from "@/components/MunkafelajanlasContent";
import { getCimzettListak, getEmployees, getMunkafelajanlasok, getMyPagePermissions, getProjects } from "@/lib/api";
import { canDoPageAction } from "@/lib/permissions";

const PAGE = "/munkafelajanlasok";

/** MUNKAFELAJÁNLÁSOK: ajánlatkérések külsősöknek. A folyamat: feladat ->
 * meghívottak -> személyre szóló ajánlatkérő e-mailek -> árajánlatok a
 * válaszadási határidőig -> BELSŐ kiválasztás a határidő után -> értesítések.
 * Senki nem kapja meg automatikusan a munkát (lásd backend
 * models/munkafelajanlas.py). */
export default async function MunkafelajanlasokPage() {
  const [ajanlatkeresek, employees, projects, cimzettListak, pagePermissions] = await Promise.all([
    getMunkafelajanlasok(),
    getEmployees(),
    getProjects(),
    getCimzettListak(),
    getMyPagePermissions(),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <MunkafelajanlasContent
          kezdeti={ajanlatkeresek}
          employees={employees}
          // A projekt a MEGLÉVŐ projektek közül választható (a felhasználó
          // kérése) - a kereső a projektkódot is mutatja az azonosításhoz.
          projektek={projects.map((p) => ({
            id: p.id,
            nev: p.nev,
            kod: p.projektkod_szoveg ?? null,
            // A forgatás dátuma is látszik a választóban (a felhasználó
            // kérése) - azonos nevű projekteknél e nélkül nem lehet dönteni.
            datum: p.forgatas_datuma ? p.forgatas_datuma.slice(0, 10) : null,
          }))}
          kezdetiListak={cimzettListak}
          canCreate={canDoPageAction(pagePermissions, PAGE, "create")}
          canEdit={canDoPageAction(pagePermissions, PAGE, "edit")}
          canDelete={canDoPageAction(pagePermissions, PAGE, "delete")}
        />
      </div>
    </div>
  );
}
