import { MegrendeloiPapirokOldal } from "@/components/megrendeloi/MegrendeloiPapirokOldal";

/** Megrendelői (eseti) szerződések gyűjtőoldala - az Eseti szerződések oldal
 * párja a megrendelői oldalon. Az ÁLLÓ keretszerződések nincsenek itt: azoknak
 * külön oldaluk van (/projektek/megrendeloi-keretszerzodesek). */
export default function MegrendeloiSzerzodesekPage() {
  return (
    <MegrendeloiPapirokOldal
      fajta="szerzodes"
      cim="Megrendelői szerződések"
      leiras="Minden projektkódhoz készült eseti szerződés a megrendelő felé."
    />
  );
}
