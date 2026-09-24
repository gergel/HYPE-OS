/** Felugró ablakos megnyitás közös szabályai - EGY helyen, hogy a beágyazott
 * nézet link-kezelője (components/EmbedNavigacio.tsx) és az alkalmazás
 * felugró-ablak kezelője (components/FelugroAblak.tsx) ugyanazt tudja.
 *
 * Az ablak iframe-ben az /embed/* keret nélküli párt tölti be (lásd
 * components/RecordDetailModal.tsx) - tehát csak az nyitható felugróban,
 * aminek VAN ilyen párja (app/embed/*). */

//: Amely útvonal-mintáknak VAN keret nélküli (/embed) párja - lásd app/embed/*.
export const EMBED_MINTAK: RegExp[] = [
  /^\/agi\/\d+$/,
  /^\/belsos-tig\/\d+\/\d+\/\d+$/,
  /^\/csapat\/\d+$/,
  /^\/feladatok\/\d+$/,
  /^\/felszereles\/\d+$/,
  /^\/flora\/\d+$/,
  /^\/hype-todo-lista\/\d+$/,
  /^\/kampanyok\/\d+$/,
  /^\/media-portal\/anyagbekeres\/\d+$/,
  /^\/media-portal\/\d+$/,
  /^\/penzugyek\/bevetel\/\d+$/,
  /^\/penzugyek\/kiadas\/\d+$/,
  /^\/projektek\/project-kodok\/\d+$/,
  /^\/projektek\/\d+$/,
  /^\/rekord\/[^/]+\/\d+$/,
  /^\/szerzodesek\/\d+$/,
  /^\/ugyfelek\/\d+$/,
  /^\/utokovetes\/projektkodok\/\d+$/,
  /^\/utokovetes\/\d+$/,
  /^\/utomunka\/\d+$/,
];

/** Van-e az útvonalnak keret nélküli (/embed) párja? A lekérdezés-rész és a
 * horgony nem számít. */
export function vanEmbedParja(href: string): boolean {
  const utvonal = href.split("?")[0].split("#")[0];
  return EMBED_MINTAK.some((m) => m.test(utvonal));
}

/** Azok a TERÜLETEK, ahol minden megnyitás felugró ablakban történik (a
 * felhasználó kérése): a teljes Pénzügyek csoport és a projektkódok - a
 * lista és az adatlap is. */
export const FELUGRO_TERULETEK: RegExp[] = [/^\/penzugyek(\/|$)/, /^\/projektek\/project-kodok(\/|$)/];

export function felugroTerulet(pathname: string): boolean {
  return FELUGRO_TERULETEK.some((m) => m.test(pathname));
}
