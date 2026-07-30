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
