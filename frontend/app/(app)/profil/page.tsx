import { TopBar } from "@/components/TopBar";
import { Card } from "@/components/Card";
import { ProfilSzerkeszto } from "@/components/ProfilSzerkeszto";
import { getCurrentUser } from "@/lib/api";

/** A SAJÁT PROFIL oldala (a felhasználó kérése) - a fejléc avatárjáról nyílik.
 * Itt állítható a profilkép és a saját szín: a név ezen a színen jelenik meg
 * pl. az utómunka kártyákon (lásd DeliverableBoard). Önkiszolgáló: mindenki
 * csak a sajátját szerkeszti (a backend a tokenből tudja, kiről van szó),
 * ezért nincs hozzá külön oldal-jogosultság. */
export default async function ProfilPage() {
  const user = await getCurrentUser();

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-4 md:p-8">
        <div className="mx-auto max-w-2xl">
          <Card title="Profilom">
            {user ? (
              <ProfilSzerkeszto
                nev={user.full_name}
                email={user.email}
                kezdetiSzin={user.szin ?? null}
                kezdetiKep={user.profilkep ?? null}
              />
            ) : (
              <p className="text-[13px] text-text-muted">Nem sikerült betölteni a profilodat - frissítsd az oldalt.</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
