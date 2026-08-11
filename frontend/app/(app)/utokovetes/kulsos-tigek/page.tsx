import Link from "next/link";
import { Card } from "@/components/Card";
import { KulsosTigLista } from "@/components/KulsosTigLista";
import { TopBar } from "@/components/TopBar";
import { formatHuf, getKulsosTigek } from "@/lib/api";

/** Külsős teljesítési igazolások: MINDEN TIG egy listában, a KIHAGYOTTAKKAL
 * együtt.
 *
 * Az Eseti szerződések oldal párja a TIG oldalán, és ugyanazért kell: eddig
 * csak szétszórva lehetett rájuk látni - projektenként az Utókövetésen,
 * emberenként a munkatárs adatlapján -, tehát arra a kérdésre, hogy "hol tart
 * összességében a külsős TIG-ezés", nem volt hely, ahol válasz lett volna.
 *
 * A kihagyottak azért vannak benne, mert egy kihagyott TIG ugyanúgy elszámolás,
 * mint egy kiküldött, csak papír nélkül - és pont az a néhány tétel, amit
 * később a legvalószínűbben számon kérnek. Az indokuk is itt látszik.
 *
 * A belsős TIG-ek NEM tartoznak ide: azok haviak, nem projektenkéntiek, és
 * saját oldaluk van (lásd /belsos-tig). */
export default async function KulsosTigekPage() {
  const rows = await getKulsosTigek();

  const kikuldott = rows.filter((t) => t.allapot === "Kiküldve").length;
  const kihagyott = rows.filter((t) => t.allapot === "Kihagyva").length;
  const keszul = rows.length - kikuldott - kihagyott;
  const kifizetve = rows.filter((t) => t.szamla_kifizetve).length;
  const osszesNetto = rows.reduce((sum, t) => sum + (t.netto_osszeg ?? 0), 0);

  return (
    <div className="flex flex-1 flex-col">
      <TopBar />
      <div className="flex-1 p-8">
        <Card title={`Külsős teljesítési igazolások (${rows.length})`}>
          <p className="mb-3 text-[12.5px] text-text-muted">
            {kikuldott} kiküldve, {kihagyott} kihagyva, {keszul} készül. {kifizetve} számla ki van fizetve. Összesen{" "}
            {formatHuf(osszesNetto)} nettó. A kihagyottaknál az indok is itt látszik. A havi belsős TIG-ek a{" "}
            <Link href="/belsos-tig" className="text-text-accent hover:underline">
              Belsős TIG
            </Link>{" "}
            oldalon vannak.
          </p>
          <KulsosTigLista rows={rows} />
        </Card>
      </div>
    </div>
  );
}
