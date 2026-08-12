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

export function canDoAction(
  forras: SzerepkorForras,
  pagePermissions: Record<string, string[]> | null,
  page: string,
  action: "create" | "edit" | "delete",
): boolean {
  if (vedettAdmin(forras)) return true;
  if (!szerepkorei(forras).some((r) => WRITE_ROLES.has(r))) return false;
  if (pagePermissions === null) return true;
  return !!pagePermissions[page]?.includes(action);
}
