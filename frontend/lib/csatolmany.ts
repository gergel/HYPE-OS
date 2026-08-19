/** A diszpó levélhez csatolható fájlok EGYÜTTES mérethatára.
 *
 * Ezek a fájlok nem csak tárolódnak: a diszpó kiküldésekor a levél
 * mellékleteként ki is mennek a stábnak. A Gmail üzenetkorlátja 25 MB, a
 * base64 kódolás ~33%-kal növeli a méretet, és a levélben ott van a diszpó
 * PDF is - innen a 15 MB.
 *
 * A számot a backend kényszeríti ki (services/attachments.py DISZPO_MAX_BAJT
 * és services/dispo.py MAX_CSATOLMANY_BAJT); itt csak azért ismételjük meg,
 * hogy a felület előre szóljon, és ne egy hosszú feltöltés végén derüljön ki. */
export const DISZPO_MAX_BAJT = 15 * 1024 * 1024;

/** Mit tegyen a felhasználó a nagy fájllal. A brief szövege a diszpóval
 * generált PDF-be is bekerül (lásd backend services/dispo.py), tehát az oda
 * beírt Drive-link így is eljut a stábhoz. */
export const DISZPO_MERET_TANACS =
  "Ami nem fér bele: töltsd fel Google Drive-ra, és a linkjét tedd be a projekt briefjébe - a brief a diszpóval együtt megy ki.";

/** Fájlok feltöltése egy MÁR LÉTEZŐ rekordhoz.
 *
 * Azért külön függvény, mert a felviteli űrlapokon a fájl előbb van meg, mint
 * a rekord: a csatolmány végpontnak viszont kell az entity_id (lásd backend
 * routes/attachments.py). A megoldás mindenhol ugyanaz - előbb mentjük a
 * rekordot, aztán az így kapott id-vel töltjük fel a fájlokat.
 *
 * Visszatérés: `null`, ha minden feltöltés sikerült, különben a hibaüzenet.
 * SZÁNDÉKOSAN nem dob: a hívó a rekordot már elmentette, tehát a hiba nem
 * "sikertelen mentés", hanem "a tétel megvan, a fájl nem ment fel" - és ezt
 * másképp kell megmondani. */
export async function toltsdFelAFajlokat(
  entityType: string,
  entityId: number,
  fajlok: File[],
  kategoria = "szamla",
): Promise<string | null> {
  // DINAMIKUS import: ezt a modult SZERVER-komponens is behúzza (a diszpó
  // mérethatár konstansaiért), a lib/authFetch viszont "use client" - egy
  // felső szintű import onnan a szerver-oldali renderelést törné el. Így a
  // kliens-modul csak akkor kerül elő, amikor tényleg feltöltünk, azaz a
  // böngészőben.
  const { authFetch } = await import("@/lib/authFetch");
  for (const fajl of fajlok) {
    const fd = new FormData();
    fd.append("file", fajl);
    const ujraSzoveg = "A listában a sor mellett újra megpróbálhatod.";
    try {
      const res = await authFetch(`/api/v1/csatolmanyok/${entityType}/${entityId}?kategoria=${kategoria}`, {
        method: "POST",
        body: fd,
      });
      if (!res.ok) {
        const reszlet = await res.json().catch(() => null);
        return `A tétel elmentve, de a fájl nem ment fel („${fajl.name}”): ${reszlet?.detail ?? `HTTP ${res.status}`}. ${ujraSzoveg}`;
      }
    } catch (err) {
      return `A tétel elmentve, de a fájl nem ment fel („${fajl.name}”): ${err}. ${ujraSzoveg}`;
    }
  }
  return null;
}
