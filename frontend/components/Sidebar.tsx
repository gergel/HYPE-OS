import { Logo } from "@/components/Logo";
import { NavList } from "@/components/NavList";

/** Az ASZTALI oldalsáv - telefonon rejtve marad (lásd MobileNav.tsx a
 * mobil-fiókért), mert a hely nem elég egy állandóan látszó, 248px széles
 * sávnak.
 *
 * allowedPages: az egyénenként beállított oldal-hozzáférés (lásd Beállítások) -
 * null = minden oldal látszik, egyébként csak azok, amiknek a permissionPage-e
 * (vagy ha az nincs megadva, a href-je) szerepel a listában - lásd
 * NavItem.permissionPage kommentje arról, miért nem elég a puszta URL első
 * szegmense. A tényleges belépés-blokkolást a middleware végzi, ez csak a
 * navigáció elrejtése.
 *
 * anyagKorlat: ha nem null, a felhasználó CSAK a rábízott utómunka-anyagokat
 * láthatja (külsős vágó fiókja) - neki a menüben egyáltalán nincs mire
 * navigálni: a Dashboard maga a teendő-listája, az anyag pedig felugró
 * ablakban nyílik (lásd KorlatozottDashboard). */
export function Sidebar({
  allowedPages,
  pagePermissions = null,
  anyagKorlat = null,
}: {
  allowedPages: string[] | null;
  pagePermissions?: Record<string, string[]> | null;
  anyagKorlat?: number[] | null;
}) {
  return (
    <aside className="hidden w-[248px] shrink-0 flex-col border-r border-border bg-surface-1 px-3 py-6 md:flex">
      <div className="mb-8 px-3">
        <Logo />
      </div>
      <NavList allowedPages={allowedPages} pagePermissions={pagePermissions} anyagKorlat={anyagKorlat} />
    </aside>
  );
}
