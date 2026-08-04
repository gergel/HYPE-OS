import { getCurrentUser, getNotifications } from "@/lib/api";
import { GlobalSearch } from "@/components/GlobalSearch";
import { NotificationBell } from "@/components/NotificationBell";
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
  const [user, notifications] = await Promise.all([getCurrentUser(), getNotifications()]);
  const today = formatHuDate(new Date());
  const greeting = greetingForHour(new Date().getHours());
  const name = user?.full_name ?? "";
  const initials = user ? initialsFromName(user.full_name) : "?";

  return (
    /* A fejléc a vázhoz tartozik, nem a tartalomhoz: ugyanaz a sötétebb
       felület, mint az oldalsávé, és megtapad görgetéskor - így a kereső és a
       kijelentkezés mindig kéznél van. */
    <div
      data-app-chrome
      className="sticky top-0 z-20 flex items-center justify-between gap-6 border-b border-border bg-surface-1/85 px-8 py-5 backdrop-blur-xl"
    >
      <div className="min-w-0">
        <p className="text-[15px] font-medium tracking-[-0.01em] text-text-primary">
          {greeting}
          {name ? `, ${name}` : ""}
        </p>
        <p className="mt-1 text-[12.5px] text-text-muted">{today}</p>
      </div>
      <div className="flex items-center gap-2.5">
        <GlobalSearch />
        <NotificationBell initial={notifications} />
        <UserMenu name={name || "Ismeretlen"} email={user?.email ?? null} initials={initials} />
      </div>
    </div>
  );
}
