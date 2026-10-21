import { redirect } from "next/navigation";
import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { BejovoSzamlak } from "@/components/finance/BejovoSzamlak";
import { getAutok, getBejovoSzamlak, getEmployees, getMyPagePermissions, getProjectCodes } from "@/lib/api";

const PAGE = "/penzugyek";

/** BEÉRKEZŐ SZÁMLÁK - a számla-érkeztető ellenőrző felülete.
 *
 * Ide fut be minden, ami a szamla@ címre e-mailben érkezik, vagy amit az AI
 * Assistantba dobtak be: a rendszer kiolvassa, megkeresi a helyét, és
 * piszkozatként ide teszi - a felhasználó ellenőriz és jóváhagy. Éles kiadás/
 * TIG-számla KIZÁRÓLAG a jóváhagyáskor születik (lásd backend
 * services/szamla_erkeztetes.py). */
export default async function BejovoSzamlakPage() {
  const pagePermissions = await getMyPagePermissions();
  const canView = pagePermissions === null || !!pagePermissions[PAGE]?.includes("view");
  if (!canView) redirect("/nincs-jogosultsag");
  const canEdit = pagePermissions === null || !!pagePermissions[PAGE]?.includes("edit");
  const canCreate = pagePermissions === null || !!pagePermissions[PAGE]?.includes("create");
  const canDelete = pagePermissions === null || !!pagePermissions[PAGE]?.includes("delete");

  const [lista, projektkodok, emberek, autok] = await Promise.all([
    getBejovoSzamlak(),
    getProjectCodes(),
    getEmployees(),
    getAutok(),
  ]);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 space-y-6 p-4 md:p-8">
        <Card title="Beérkező számlák">
          <p className="mb-4 text-[12.5px] text-text-secondary">
            A számla beérkezik (e-mailben vagy az AI Assistantba dobva), a rendszer kiolvassa és előkészíti a
            megfelelő helyre - itt csak ellenőrizni és jóváhagyni kell. A jóváhagyásig semmilyen éles összesítés
            nem változik, és a jóváhagyott számla sem válik automatikusan kifizetetté.
          </p>
          <BejovoSzamlak
            kezdoLista={lista}
            valasztek={{
              projektkodok: projektkodok.map((p) => ({ id: p.id, kod: p.projektkod })),
              emberek: emberek.map((e) => ({ id: e.id, nev: e.full_name })),
              autok: autok.map((a) => ({ id: a.id, nev: `${a.rendszam}${a.tipus ? ` – ${a.tipus}` : ""}` })),
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
