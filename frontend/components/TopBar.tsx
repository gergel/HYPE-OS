import { getCurrentUser } from "@/lib/api";
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
  const user = await getCurrentUser();
  const today = formatHuDate(new Date());
  const greeting = greetingForHour(new Date().getHours());
  const name = user?.full_name ?? "";
  const initials = user ? initialsFromName(user.full_name) : "?";

  return (
    <div className="flex items-center justify-between gap-4 border-b border-border px-6 py-4">
      <div>
        <p className="text-lg font-medium text-text-primary">
          {greeting}
          {name ? `, ${name}` : ""}! <span aria-hidden>👋</span>
        </p>
        <p className="mt-0.5 text-[13px] text-text-secondary">{today}</p>
      </div>
      <div className="flex items-center gap-3">
        <label className="hidden items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-1 px-3 py-1.5 text-text-muted md:flex">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            type="text"
            placeholder="Keresés bármiben…"
            className="w-40 bg-transparent text-[13px] text-text-primary placeholder:text-text-muted focus:outline-none lg:w-64"
          />
        </label>
        <button
          type="button"
          aria-label="Értesítések"
          className="rounded-full border border-border p-2 text-text-secondary hover:bg-surface-3"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
        </button>
        <UserMenu name={name || "Ismeretlen"} email={user?.email ?? null} initials={initials} />
      </div>
    </div>
  );
}
