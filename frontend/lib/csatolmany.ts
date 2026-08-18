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
