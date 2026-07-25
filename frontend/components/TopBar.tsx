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
    <div data-app-chrome className="flex items-center justify-between gap-4 border-b border-border px-6 py-4">
      <div>
        <p className="text-lg font-medium text-text-primary">
          {greeting}
          {name ? `, ${name}` : ""}! <span aria-hidden>👋</span>
        </p>
        <p className="mt-0.5 text-[13px] text-text-secondary">{today}</p>
      </div>
      <div className="flex items-center gap-3">
        <GlobalSearch />
        <NotificationBell initial={notifications} />
        <UserMenu name={name || "Ismeretlen"} email={user?.email ?? null} initials={initials} />
      </div>
    </div>
  );
}
