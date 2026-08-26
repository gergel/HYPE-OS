/** Melyik oldalon MI változhat - ez alapján tudja a háttérfrissítés, hogy mit
 * kell figyelnie, anélkül hogy minden egyes oldalt módosítani kellene.
 *
 * A témanevek a backend TOPICS listájából jönnek (app/api/routes/realtime.py);
 * ismeretlen nevet a szerver csendben kihagy, tehát egy elgépelés nem hibázik
 * el egy oldalt, csak nem frissül tőle.
 *
 * A minták sorrendje NEM számít: a leghosszabb egyező előtag nyer, így a
 * "/projektek/12" a részletnézet témáit kapja, nem a listáét. */

/** Minden oldalon figyeljük: az értesítés-csengő a fejlécben mindenhol ott van. */
const ALWAYS: string[] = ["notifications"];

const BY_PREFIX: Record<string, string[]> = {
  "/dashboard": ["tasks", "projects", "deliverables"],
  "/naptar": ["projects"],
  "/projektek": ["projects"],
  // A "kifizetve" jelölés (fájlonként vagy projekt-szinten) a `revenues` és a
  // `documentAttachments` táblát írja, NEM mindig magát a projektkódot (lásd
  // services/megrendeloi_szamla.jelold_szamlat_kifizetettnek) - enélkül a
  // teendő-tábla csak akkor frissült volna, ha VALAMI MÁS is megérintette
  // közben a projektkód sorát, tehát a kifizetett tétel percekig (vagy tovább)
  // benne maradt a teendők közt, amíg valaki manuálisan újra nem töltötte.
  // Az "expenses" ugyanezért kell: a projektkód adatlapján felvett/szerkesztett
  // kiadás UGYANAZ a rekord, mint a Pénzügyek → Kiadások listáján (lásd
  // ProjektkodBontasTablak "+ Új kiadás") - enélkül a Pénzügyeken végzett
  // szerkesztés csak kézi újratöltéssel látszott volna itt.
  "/projektek/project-kodok": ["projectCodes", "projects", "revenues", "documentAttachments", "expenses"],
  // A hozzászólásokat nem itt figyeljük: a chat komponens a saját anyagára
  // szűkítve iratkozik fel ("comments:12"), különben egy másik anyag alatti
  // hozzászólás is frissítené ezt az oldalt.
  "/utomunka": ["deliverables", "timesheets"],
  "/feladatok": ["tasks"],
  "/csapat": ["employees", "rates", "internalPerformanceCertificates"],
  "/felszereles": ["equipment", "assignments"],
  "/felszereles/leltarazas": ["stocktakes", "equipment"],
  "/ugyfelek": ["clients", "contacts"],
  "/kampanyok": ["campaigns"],
  "/penzugyek": ["expenses", "revenues", "kpForgalmak"],
  "/penzugyek/keretszerzodesek": ["contracts"],
  "/penzugyek/eseti-szerzodesek": ["contracts", "projects"],
  "/alvallalkozoi-szerzodesek": ["contracts", "projects"],
  "/szerzodesek": ["contracts"],
  "/teljesitesi-igazolasok": ["performanceCertificates", "internalPerformanceCertificates", "projects"],
  "/belsos-tig": ["internalPerformanceCertificates"],
  "/utokovetes": ["projects", "postShootFeedbacks", "performanceCertificates", "contracts"],
  "/media-portal": ["portals"],
};

/** A projekt részletnézet (/projektek/12) sokféle alrekordot mutat egy oldalon:
 * stáb, technika, diszpó, szerződés, TIG. A lista (/projektek) viszont csak
 * magukat a projekteket - fölösleges lenne ott mindent figyelni. */
const PROJECT_DETAIL_TOPICS = [
  "projects",
  "assignments",
  "callsheets",
  "contracts",
  "performanceCertificates",
  "deliverables",
];

function isDetailPath(pathname: string, listPath: string): boolean {
  if (!pathname.startsWith(`${listPath}/`)) return false;
  const rest = pathname.slice(listPath.length + 1);
  return /^\d+$/.test(rest);
}

export function topicsForPath(pathname: string): string[] {
  // Az /embed/... nézetek ugyanazok a részletoldalak, csak keret nélkül.
  const path = pathname.startsWith("/embed/") ? pathname.slice("/embed".length) : pathname;

  if (isDetailPath(path, "/projektek")) return [...ALWAYS, ...PROJECT_DETAIL_TOPICS];

  let best = "";
  for (const prefix of Object.keys(BY_PREFIX)) {
    if ((path === prefix || path.startsWith(`${prefix}/`)) && prefix.length > best.length) best = prefix;
  }
  return best ? [...ALWAYS, ...BY_PREFIX[best]] : ALWAYS;
}
