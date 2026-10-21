import { TopBar } from "@/components/TopBar";
import { AnyagbekeresekPanel, type BekeresSor } from "@/components/anyagbekeres/AnyagbekeresekPanel";
import { getAnyagbekeresek, getClients, getEmployees, getMyPagePermissions, getProjects } from "@/lib/api";

/** ANYAGBEKÉRÉSEK - admin lista (a Media Portal jogosultságával). */
export default async function AnyagbekeresekOldal() {
  const [sorok, projektek, ugyfelek, munkatarsak, pagePermissions] = await Promise.all([
    getAnyagbekeresek(),
    getProjects(),
    getClients(),
    getEmployees(),
    getMyPagePermissions(),
  ]);
  const canCreate = pagePermissions === null || !!pagePermissions["/media-portal"]?.includes("create");
  const canDelete = pagePermissions === null || !!pagePermissions["/media-portal"]?.includes("delete");
  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <AnyagbekeresekPanel
        kezdeti={sorok as unknown as BekeresSor[]}
        projektek={projektek.map((p) => ({ id: p.id, nev: p.nev }))}
        ugyfelek={ugyfelek.map((u) => ({ id: u.id, nev: u.nev }))}
        munkatarsak={munkatarsak.filter((m) => m.is_active).map((m) => ({ id: m.id, nev: m.full_name }))}
        canCreate={canCreate}
        canDelete={canDelete}
      />
    </div>
  );
}
