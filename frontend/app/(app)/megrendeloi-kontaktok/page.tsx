import { Card } from "@/components/Card";
import { TopBar } from "@/components/TopBar";
import { KontaktLista } from "@/components/kontakt/KontaktLista";
import { getClients, getCurrentUser, getMegrendeloiKontaktok, getMyPagePermissions } from "@/lib/api";
import { canDoAction } from "@/lib/permissions";

// A kontaktok az Ügyfelek adatához tartoznak, ezért annak a jogosultságát
// használják - ez az oldal csak egy másik nézet ugyanarra (lásd backend
// routes/megrendeloi_kontaktok.py).
const PAGE = "/ugyfelek";

/** Megrendelői kontaktok - kikkel tartjuk a kapcsolatot az ügyfél oldalán.
 *
 * Eddig is léteztek (a Notion "Megrendelői kontaktok" táblájából jönnek), de
 * csak az ügyfél adatlapjába zárva: nem lehetett rákeresni valakire anélkül,
 * hogy tudnánk, melyik cégnél van, és nem látszott, kinek megy ténylegesen
 * anyag. Ez az oldal mindkettőt megadja - plusz egy gombot, amivel a látható
 * kontaktok email címei egyben a vágólapra kerülnek. */
export default async function MegrendeloiKontaktokPage() {
  const [kontaktok, clients, currentUser, pagePermissions] = await Promise.all([
    getMegrendeloiKontaktok(),
    getClients(),
    getCurrentUser(),
    getMyPagePermissions(),
  ]);

  const ugyfelek = clients
    .map((c) => ({ id: c.id, nev: c.nev }))
    .sort((a, b) => a.nev.localeCompare(b.nev, "hu"));
  const emailesek = kontaktok.filter((k) => (k.email ?? "").trim()).length;
  const anyaggal = kontaktok.filter((k) => k.anyagok_szama > 0).length;

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <Card title={`Megrendelői kontaktok (${kontaktok.length})`}>
          <p className="mb-4 text-[13px] text-text-secondary">
            Kikkel tartjuk a kapcsolatot az ügyfeleknél. {emailesek} kontaktnak van email címe
            {anyaggal > 0 && <>, {anyaggal} pedig be van állítva valamelyik anyag kiküldéséhez</>}. Azt, hogy egy
            konkrét anyagot kiknek kell kiküldeni, az Utómunka oldalon, az anyag „Megrendelői kontaktok" fülén
            lehet megadni.
          </p>
          <KontaktLista
            kontaktok={kontaktok}
            ugyfelek={ugyfelek}
            canEdit={canDoAction(currentUser, pagePermissions, PAGE, "edit")}
            canCreate={canDoAction(currentUser, pagePermissions, PAGE, "create")}
            canDelete={canDoAction(currentUser, pagePermissions, PAGE, "delete")}
          />
        </Card>
      </div>
    </div>
  );
}
