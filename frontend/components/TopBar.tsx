import { getCurrentUser, getMyAccess, getNotifications } from "@/lib/api";
import { GlobalSearch } from "@/components/GlobalSearch";
import { KrumpelloKapcsolo } from "@/components/KrumpelloKapcsolo";
import { MobileNav } from "@/components/MobileNav";
import { NotificationBell } from "@/components/NotificationBell";
import { TemaKapcsolo } from "@/components/TemaKapcsolo";
import { UserMenu } from "@/components/UserMenu";

const WEEKDAYS = ["vasárnap", "hétfő", "kedd", "szerda", "csütörtök", "péntek", "szombat"];
const MONTHS = [
  "január",
  "február",
  "március",
  "április",
  "május",
  "június",
  "július",
  "augusztus",
  "szeptember",
  "október",
  "november",
  "december",
];

function formatHuDate(date: Date): string {
  return `${date.getFullYear()}. ${MONTHS[date.getMonth()]} ${date.getDate()}., ${WEEKDAYS[date.getDay()]}`;
}

function greetingForHour(hour: number): string {
  if (hour < 10) return "Jó reggelt";
  if (hour < 18) return "Jó napot";
  return "Jó estét";
}

function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Minden oldalon megjelenő fejléc - a bejelentkezett felhasználó nevével
 * köszönt (napszaknak megfelelően), és bárhonnan elérhető a kijelentkezés
 * (lásd UserMenu), nem csak a Beállítások oldalról. */
export async function TopBar() {
  const [user, notifications, access] = await Promise.all([
    getCurrentUser(),
    getNotifications(),
    getMyAccess(),
  ]);
  const today = formatHuDate(new Date());
  const greeting = greetingForHour(new Date().getHours());
  const name = user?.full_name ?? "";
  const initials = user ? initialsFromName(user.full_name) : "?";

  return (
    /* A fejléc a vázhoz tartozik, nem a tartalomhoz: ugyanaz a sötétebb
       felület, mint az oldalsávé, és megtapad görgetéskor - így a kereső és a
       kijelentkezés mindig kéznél van.

       Telefonon a Sidebar (asztali oldalsáv) teljesen eltűnik - a hamburger-
       gomb (MobileNav) itt jelenik meg, mert a TopBar-t minden oldal maga
       hordozza, a Sidebar-t adó (app)/layout.tsx-szel ellentétben. A
       köszöntés/dátum és a jobb oldali ikonsor is összébb húzódik, hogy ne
       törjön sortöbbszörre egy keskeny képernyőn. */
    <div
      data-app-chrome
      className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-border bg-surface-1/85 px-4 py-4 backdrop-blur-xl sm:gap-6 md:px-8 md:py-5"
    >
      <div className="flex min-w-0 items-center gap-3">
        <MobileNav
          allowedPages={access.allowedPages}
          pagePermissions={access.pagePermissions}
          anyagKorlat={access.anyagKorlat}
        />
        <div className="min-w-0">
          <p className="truncate text-[14px] font-medium tracking-[-0.01em] text-text-primary sm:text-[15px]">
            {greeting}
            {name ? `, ${name}` : ""}
          </p>
          {/* A dátum a legkevésbé fontos sor - keskeny képernyőn ez esik ki
              elsőként, hogy a köszöntés egy sorban maradhasson. */}
          <p className="mt-1 hidden text-[12.5px] text-text-muted sm:block">{today}</p>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1.5 sm:gap-2.5">
        {/* Átlépés a Krumpello pénzügyre - csak jogosultsággal látszik. */}
        <KrumpelloKapcsolo />
        <GlobalSearch />
        {/* A mentett beállítás a SZERVERRŐL jön (employees.tema) - a süti
            csak az első festés gyorsítótára, lásd lib/tema.ts. */}
        <TemaKapcsolo kezdeti={user?.tema ?? null} />
        <NotificationBell initial={notifications} />
        <UserMenu name={name || "Ismeretlen"} email={user?.email ?? null} initials={initials} />
      </div>
    </div>
  );
}
