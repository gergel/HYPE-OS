/** Idő- és költségformázás az utómunka-időmérőhöz (lásd TimerControls,
 * UtomunkaIdoHavonta, VagasiKoltsegOsszesen). Egy helyen, hogy a futó mérő, a
 * havi bontás és a projekt-összesítő ugyanúgy nézzen ki. */

/** Percből "26 ó 5 p" - az óra SZÁNDÉKOSAN nincs 24-nél elvágva: egy éjszakán
 * át (vagy hétvégén át) futó mérésnél is a valós, összegzett órát kell látni,
 * nem egy 24 óránként újrainduló számot. */
export function formatPercek(minutes: number): string {
  const kerekitett = Math.round(minutes);
  const h = Math.floor(kerekitett / 60);
  const m = kerekitett % 60;
  return h > 0 ? `${h} ó ${m} p` : `${m} p`;
}

/** Eltelt idő óra:perc:másodperc alakban. 24 óra fölött NEM fordul át: a nap
 * külön elöl jelenik meg ("1 n 02:15:03"), így egy elfelejtett, több napja
 * futó mérőnél is látszik, mennyi ideje megy valójában. */
export function formatEltelt(startIso: string, now: Date): string {
  const start = new Date(startIso);
  const osszSec = Math.max(0, Math.floor((now.getTime() - start.getTime()) / 1000));
  const napok = Math.floor(osszSec / 86400);
  const h = Math.floor((osszSec % 86400) / 3600);
  const m = Math.floor((osszSec % 3600) / 60);
  const s = osszSec % 60;
  const ora = [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
  return napok > 0 ? `${napok} n ${ora}` : ora;
}

/** Két időpont közti eltelt PERC (tizedessel) - a még futó mérés élő
 * költségéhez. */
export function elteltPercek(startIso: string, now: Date): number {
  const start = new Date(startIso);
  return Math.max(0, (now.getTime() - start.getTime()) / 60000);
}

/** A még futó mérés költsége a mérés indításakor rögzített órabérrel - ugyanaz
 * a képlet, amit leállításkor a backend is használ (lásd
 * services/deliverable_actions.szamolt_koltseg), hogy a Stop pillanatában ne
 * ugorjon meg az összeg. */
export function futoKoltseg(startIso: string, orabere: number | null, now: Date): number {
  if (orabere === null) return 0;
  return (elteltPercek(startIso, now) / 60) * orabere;
}

/** Pontos forintösszeg csoportosítva ("1 234 567 Ft") - a formatHuf-fal
 * ellentétben nem rövidít "1.2M"-re, mert a munkaidő-költségeknél a pontos
 * összeg számít. */
export function formatFt(value: number): string {
  return `${Math.round(value).toLocaleString("hu-HU")} Ft`;
}

/** A hónapok magyar neve (1 = január). Egy helyen, mert a havi elszámolás
 * több felületen is hónapnevet ír ki (havi kiadások, egyéb kiadások). */
export const HONAP_NEVEK = [
  "január", "február", "március", "április", "május", "június",
  "július", "augusztus", "szeptember", "október", "november", "december",
];

/** "2026. május" - egy elszámolási hónap emberi neve. */
export function honapCimke(ev: number, honap: number): string {
  return `${ev}. ${HONAP_NEVEK[honap - 1] ?? honap}`;
}

/** ISO időbélyeg -> "2026. 08. 04. 14:32". Ott kell, ahol nem az eltelt idő,
 * hanem a KONKRÉT időpont a lényeg (pl. mikor állították le a vágást) - a
 * puszta dátum ebből épp a napon belüli időt dobná el. */
export function formatIdopont(value: string | null | undefined): string {
  if (!value) return "–";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "–";
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}. ${p(d.getMonth() + 1)}. ${p(d.getDate())}. ${p(d.getHours())}:${p(d.getMinutes())}`;
}
