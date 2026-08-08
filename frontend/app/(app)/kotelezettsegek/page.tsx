import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { KotelezettsegKezelo } from "@/components/kotelezettseg/KotelezettsegKezelo";
import { getCurrentUser, getEmployees, getKotelezettsegek, getMyPagePermissions } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

const PAGE = "/kotelezettsegek";

/** Biztosítások és egyéb lejáró kötelezettségek.
 *
 * Ami itt van, arról a rendszer SZÓL, mielőtt lejár: a fordulóhoz közeledve
 * feladat készül a felelősnek, és értesítést is kap róla (lásd backend
 * services/kotelezettseg.py ensure_feladatok). A figyelmeztetés ideje
 * soronként állítható - egy éves biztosításnál két hét kevés lehet.
 *
 * Az előfizetések ugyanezen a motoron futnak, de saját oldalon (E-Rezsi), az
 * autók papírjai pedig az adott jármű lapján - hogy ez a lista ne folyjon
 * össze a havi szolgáltatásokkal. */
export default async function KotelezettsegekPage() {
  const [kotelezettsegek, employees, currentUser, pagePermissions] = await Promise.all([
    // Minden, ami nem előfizetés és nem egy autó papírja - azoknak saját
    // oldaluk van.
    getKotelezettsegek({ tipus: "biztositas,berlet,egyeb" }),
    getEmployees(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);

  const sajat = kotelezettsegek.filter((k) => k.auto_id == null);
  const lejart = sajat.filter((k) => k.aktiv && k.allapot === "lejart").length;
  const hamarosan = sajat.filter((k) => k.aktiv && k.allapot === "hamarosan").length;

  const emberek = employees
    .map((e) => ({ id: e.id, full_name: e.full_name }))
    .sort((a, b) => a.full_name.localeCompare(b.full_name, "hu"));

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Biztosítások és lejáró kötelezettségek (${sajat.length})`}>
          <p className="mb-4 text-[13px] text-text-secondary">
            {sajat.length === 0
              ? "Még nincs felvéve egy sem. Amit ide felviszel, arról a rendszer szól, mielőtt lejár."
              : `${sajat.filter((k) => k.aktiv).length} aktív${lejart > 0 ? ` · ${lejart} lejárt` : ""}${
                  hamarosan > 0 ? ` · ${hamarosan} hamarosan lejár` : ""
                }. A felelős a forduló előtt feladatot és értesítést kap.`}
          </p>
          <KotelezettsegKezelo
            kotelezettsegek={sajat}
            emberek={emberek}
            alapTipus="biztositas"
            canEdit={canDoAction(currentUser, pagePermissions, PAGE, "edit")}
            canCreate={canDoAction(currentUser, pagePermissions, PAGE, "create")}
            canDelete={canDoAction(currentUser, pagePermissions, PAGE, "delete")}
          />
        </Card>
      </div>
    </div>
  );
}
