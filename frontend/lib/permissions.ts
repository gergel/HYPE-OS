/** Kliens-oldali (SSR) segédfüggvény annak eldöntésére, hogy a bejelentkezett
 * felhasználó lásson-e létrehozás/törlés UI-t egy adott oldalon - PUSZTÁN
 * megjelenítési célra (ne mutasson gombot, amire úgyis 403-at kapna), a
 * tényleges kikényszerítés mindig a backend oldalon történik (lásd
 * core/security.require_roles + check_page_action,
 * api/crud_router.py create_dependency/delete_dependency).
 *
 * A generikus CRUD végpontok write_roles alapértelmezetten csak admin/operator
 * szerepkörnek engedik a létrehozást/törlést (lásd build_crud_router) - ezt a
 * durvább szerepkör-ellenőrzést a page_permissions (ha be van állítva)
 * tovább szűkítheti, de sosem bővítheti. Ezért mindkét feltételnek teljesülnie
 * kell. */
/** Ugyanaz, mint a backend DEFAULT_WRITE_ROLES (lásd core/security.py) - az
 * Adminisztráció szerepkör azért írhat, mert épp az a dolga, hogy a papírokat
 * (TIG-ek, szerződések) elkészítse. */
const WRITE_ROLES = new Set(["admin", "operator", "adminisztracio"]);

/** Akinek a szerepköreit nézzük. Egy embernek TÖBB szerepköre is lehet (pl.
 * admin ÉS adminisztráció): az elsődleges a `role`, a többi a
 * `tovabbi_szerepkorok` listában - lásd backend models/employee.szerepkorei. */
export type SzerepkorForras =
  | { role: string; tovabbi_szerepkorok?: string[] | null; vedett_admin?: boolean }
  | string
  | string[]
  | null
  | undefined;

/** VÉDETT RENDSZERGAZDA-e - neki mindent mutatunk.
 *
 * A jelölést a backend számolja a beállításból (lásd
 * core/security.vedett_rendszergazda), nem itt vezetjük le: a felület csak
 * megjeleníti, amit a szerver mond. Enélkül egy elrontott szerepkör mellett a
 * gombok akkor is eltűnnének, amikor a backend már beengedné a műveletet -
 * vagyis a felületen mégis ki lenne zárva az az egy ember, akinek mindig
 * működnie kell. */
function vedettAdmin(forras: SzerepkorForras): boolean {
  return typeof forras === "object" && forras !== null && !Array.isArray(forras) && forras.vedett_admin === true;
}

/** A forrás ÖSSZES szerepköre, egy listában. */
export function szerepkorei(forras: SzerepkorForras): string[] {
  if (!forras) return [];
  if (typeof forras === "string") return [forras];
  if (Array.isArray(forras)) return forras;
  return [forras.role, ...(forras.tovabbi_szerepkorok ?? [])];
}

/** A PROJEKTHEZ RENDELT ESZKÖZÖK (foglalás) saját jogosultsági kulcsa - nem
 * valódi oldal, csak aliaszon át kapható meg. Lásd
 * `core/security.FOGLALAS_OLDAL`. */
export const FOGLALAS_OLDAL = "/felszereles/foglalas";

/** OLDAL-ALIASZOK - a backend `core/security.OLDAL_ALIASZOK` párja.
 * Felépítés: cél oldal -> forrás oldal -> {forrás művelet: átadott műveletek}.
 * Az aliaszok nem láncolódnak.
 *
 * 1) A DISZPÓ (naptár) joga a PROJEKT oldalt is megnyitja, nézésre és
 *    szerkesztésre: aki a diszpókat viszi, annak a projekten van dolga (gyártás,
 *    technika, gyártás komment, a levél mellékletei, a két diszpó kiküldése).
 *    Létrehozni és törölni viszont nem tud projektet.
 * 2) A projekt szerkesztése a technika felvezetését is jelenti: az eszköz
 *    hozzáadása/levétele MAGA a szerkesztés. Ezért ad az "edit" itt
 *    create/delete jogot - de csak a foglalásra, magára a leltárra nem.
 * 3) Aki a projekten technikát vezet fel, a FELSZERELÉS oldalt is látja
 *    (nézésre): onnan tudja megnézni, mi van a leltárban. Bővíteni, javítani,
 *    törölni, leltározni továbbra is csak a /felszereles saját jogával lehet.
 *
 * Ha ez a két lista elcsúszik egymástól, a felület mást mutat, mint amit a
 * szerver enged - ezért a két helyet EGYÜTT kell módosítani. */
export const OLDAL_ALIASZOK: Record<string, Record<string, Record<string, readonly string[]>>> = {
  "/projektek": {
    "/naptar": { view: ["view"], edit: ["edit"] },
  },
  "/felszereles": {
    "/projektek": { view: ["view"] },
    "/naptar": { view: ["view"] },
  },
  [FOGLALAS_OLDAL]: {
    "/felszereles": { view: ["view"], create: ["create"], delete: ["delete"] },
    "/projektek": { view: ["view"], edit: ["view", "create", "delete"] },
    "/naptar": { view: ["view"], edit: ["view", "create", "delete"] },
  },
};

/** Mit tehet ezen az oldalon - az aliaszokkal együtt. `null`, ha az oldal
 * egyáltalán nem engedélyezett. */
export function oldalMuveletei(
  pagePermissions: Record<string, string[]>,
  page: string,
): Set<string> | null {
  const sajat = pagePermissions[page];
  const engedve = new Set<string>(sajat ? [...sajat, "view"] : []);
  for (const [alias, atkotes] of Object.entries(OLDAL_ALIASZOK[page] ?? {})) {
    const aliasMuveletek = pagePermissions[alias];
    if (!aliasMuveletek) continue;
    // Ha az oldal kulcsa ott van, a "view" jár rá - ugyanaz, mint a sajátnál.
    const van = new Set([...aliasMuveletek, "view"]);
    for (const [forras, atadott] of Object.entries(atkotes)) {
      if (van.has(forras)) for (const muvelet of atadott) engedve.add(muvelet);
    }
  }
  return engedve.size > 0 ? engedve : null;
}

/** Látja-e egyáltalán ezt az oldalt (az aliaszokkal együtt)? A `null`
 * page_permissions korlátozás nélküli hozzáférést jelent. */
export function lathatjaAzOldalt(pagePermissions: Record<string, string[]> | null, page: string): boolean {
  if (pagePermissions === null) return true;
  return oldalMuveletei(pagePermissions, page) !== null;
}

/** Mit tehet egy RÉSZLETNÉZET-SZEKCIÓN belül - a backend
 * `core/security.check_tab_action` párja.
 *
 * A "{page}:{tab_key}" összetett kulcs csak SZŰKÍT: ha admin nem állított be
 * ilyet, a szekció az oldal (aliaszokkal együtt számolt) jogát örökli. Enélkül
 * az aliaszon át érkező munkatárs (pl. a diszpós, akinek a /naptar joga nyitja
 * meg a projektet) mindent CSAK OLVASHATÓNAK látott volna - a gyártás és a
 * technika adatait is, amiket épp neki kell kitöltenie. */
export function canDoTabAction(
  pagePermissions: Record<string, string[]> | null,
  page: string,
  tabKey: string,
  action: string,
): boolean {
  if (pagePermissions === null) return true;
  const fulreSzabott = pagePermissions[`${page}:${tabKey}`];
  const engedve = fulreSzabott !== undefined ? new Set(fulreSzabott) : oldalMuveletei(pagePermissions, page);
  return engedve?.has(action) === true;
}

export function canDoAction(
  forras: SzerepkorForras,
  pagePermissions: Record<string, string[]> | null,
  page: string,
  action: "create" | "edit" | "delete",
): boolean {
  if (vedettAdmin(forras)) return true;
  if (!szerepkorei(forras).some((r) => WRITE_ROLES.has(r))) return false;
  if (pagePermissions === null) return true;
  return oldalMuveletei(pagePermissions, page)?.has(action) === true;
}
