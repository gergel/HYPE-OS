import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { UtalasokFelvezetese } from "@/components/finance/UtalasokFelvezetese";
import { getEmployees, getMyPagePermissions, getProjectCodes, getUtalasAdagok } from "@/lib/api";

const PAGE = "/penzugyek";

/** UTALÁSOK FELVEZETÉSE - megtörtént utalások adminisztrálása.
 *
 * Egy már elutalt számlacsomagot ZIP-ben feltöltve, az adag közös utalási
 * dátumával a rendszer felismeri a számlákat, megkeresi a hozzájuk tartozó
 * meglévő tételeket, és ellenőrzés után rögzíti a kifizetést (lásd backend
 * services/utalas_felvezetes.py). Banki utalást NEM indít. */
export default async function UtalasokPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  const canEdit = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");
  const canCreate = pagePermissions === null || !!pagePermissions[PAGE]?.includes("create");
  const canDelete = pagePermissions === null || !!pagePermissions[PAGE]?.includes("delete");

  const [adagok, projektkodok, emberek] = await Promise.all([getUtalasAdagok(), getProjectCodes(), getEmployees()]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        <Card title="Utalások felvezetése">
          <p className="mb-4 text-[12.5px] text-text-secondary">
            Megtörtént utalások adminisztrálása: feltöltesz egy ZIP-et az elutalt számlákkal, megadod az adag
            közös utalási dátumát, a rendszer párosítja a számlákat a meglévő tételekhez, te pedig ellenőrzöl és
            rögzíted a kifizetéseket. Banki utalást nem indít, és a feltöltéstől még semmi nem válik fizetetté.
            A számla vevője (jellemzően HYPE) nem dönti el az elszámolási helyet - a HYPE/Krumpello besorolás
            tételenként választható; a Krumpellóhoz sorolt tételeket egyelőre csak listázzuk.
          </p>
          <UtalasokFelvezetese
            kezdoAdagok={adagok}
            valasztek={{
              projektkodok: projektkodok.map((p) => ({ id: p.id, kod: p.projektkod })),
              emberek: emberek.map((e) => ({ id: e.id, nev: e.full_name })),
            }}
            canEdit={canEdit}
            canCreate={canCreate}
            canDelete={canDelete}
          />
        </Card>
      </div>
    </div>
  );
}
