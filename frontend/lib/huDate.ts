/** Magyar hónapnevek. A Belsős TIG mindenhol BETŰVEL írja ki a hónapot
 * (fejlécben, űrlapon, listákban), sosem számmal - lásd backend
 * services/hu_datum.py, ami ugyanezt teszi a dokumentumban és az emailben. */
export const HU_HONAPOK = [
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
] as const;

export function huHonap(honap: number): string {
  return HU_HONAPOK[honap - 1] ?? "";
}

/** 2026, 5 -> "2026. május" */
export function huEvHonap(ev: number, honap: number): string {
  return `${ev}. ${huHonap(honap)}`;
}

/** "2026-06-20" -> a TIG hónapja: MINDIG az azt megelőző hónap (a backend
 * ugyanezt számolja - lásd hu_datum.elozo_honap). Érvénytelen dátumra null. */
export function tigHonapTeljesitesbol(teljesites: string): { ev: number; honap: number } | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(teljesites);
  if (!match) return null;
  const ev = Number(match[1]);
  const honap = Number(match[2]);
  if (honap < 1 || honap > 12) return null;
  return honap === 1 ? { ev: ev - 1, honap: 12 } : { ev, honap: honap - 1 };
}

/** ISO dátum ("2026-03-01") magyaros alakban ("2026.03.01."). Üres/érvénytelen
 * érték esetén gondolatjel.
 *
 * A lib/api.ts-ben is van formatDate, de az a modul `next/headers`-t használ,
 * tehát SZERVER-ONLY - kliens komponens nem importálhat belőle futásidejű
 * dolgot, csak típust. Ez a változat tiszta függvény, bárhonnan hívható. */
export function huDatum(value: string | null | undefined): string {
  if (!value) return "–";
  const [ev, honap, nap] = value.slice(0, 10).split("-");
  return ev && honap && nap ? `${ev}.${honap}.${nap}.` : value;
}
