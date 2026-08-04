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

export function canDoAction(
  role: string | undefined | null,
  pagePermissions: Record<string, string[]> | null,
  page: string,
  action: "create" | "edit" | "delete",
): boolean {
  if (!role || !WRITE_ROLES.has(role)) return false;
  if (pagePermissions === null) return true;
  return !!pagePermissions[page]?.includes(action);
}
