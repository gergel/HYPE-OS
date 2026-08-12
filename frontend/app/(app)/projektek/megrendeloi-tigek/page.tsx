import { MegrendeloiPapirokOldal } from "@/components/megrendeloi/MegrendeloiPapirokOldal";

/** Megrendelői teljesítési igazolások gyűjtőoldala - a Külsős TIG-ek oldal
 * párja a megrendelői oldalon. A keretszerződés ezt NEM váltja ki: a keret
 * arról szól, milyen feltételekkel dolgozunk együtt, a TIG arról, hogy egy
 * konkrét munka elkészült. */
export default function MegrendeloiTigekPage() {
  return (
    <MegrendeloiPapirokOldal
      fajta="tig"
      cim="Megrendelői TIG-ek"
      leiras="Minden projektkódhoz készült teljesítési igazolás a megrendelő felé."
    />
  );
}
