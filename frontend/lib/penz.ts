/** Pénz-formázás.
 *
 * SZÁNDÉKOSAN önálló, függőség nélküli modul: kliens-komponensek is használják
 * (lásd HaviKoltsegek, BelsosTigManager), a lib/api.ts viszont a
 * `next/headers`-t is behúzza (szerver-oldali cookie-olvasáshoz) - onnan
 * importálva a kliens-bundle összeomlana. Ugyanaz a minta, mint a
 * lib/mezoNev.ts és a lib/ido.ts esetében. */
import { normalizal } from "@/lib/szoveg";

export function formatHuf(value: number | null): string {
  if (value === null) return "–";
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1).replace(".0", "")}M Ft`;
  if (Math.abs(value) >= 1_000) return `${Math.round(value / 1_000)}k Ft`;
  return `${value} Ft`;
}

/** Miért NEM számít bele ez a bevétel-sor az ÉVES bevételbe? `null`, ha
 * beleszámít.
 *
 * Ugyanaz a szabály, mint a backend `services/elszamolas.bevetel_beleszamit`
 * függvényében - két helyen kell, mert a szerver szűri az összesítőket, a
 * lista pedig kiírja soronként, hogy melyik marad ki. Ha az egyik változik,
 * a másikat is állítani kell. */
export function bevetelKihagyasOka(sor: {
  bevetel_formaja: string | null;
  beleszamit_a_bevetelekbe: boolean | null;
}): string | null {
  if ((sor.bevetel_formaja ?? "").toLowerCase().includes("nem volt tranzakc")) {
    return "Nem volt tranzakció";
  }
  if (sor.beleszamit_a_bevetelekbe === false) return "Nem kerül a bevételek közé";
  return null;
}

/** Amiben számlát szoktunk kapni/kiállítani - a backend
 * `services/penznem.PENZNEMEK` párja. */
export const PENZNEMEK = ["HUF", "EUR", "USD"] as const;

/** AHOGY LE VAN ÍRVA -> a kód, amivel dolgozunk. A backend
 * `services/penznem.PENZNEM_ALIASZOK` párja: a Notionben ez szabad select
 * volt, magyarul kitöltve, ezért a régi projektkódokon "Forint" áll, nem
 * "HUF". A kettőt együtt kell módosítani. */
const PENZNEM_ALIASZOK: Record<string, string> = {
  HUF: "HUF",
  FT: "HUF",
  FORINT: "HUF",
  "MAGYAR FORINT": "HUF",
  EUR: "EUR",
  EURO: "EUR",
  "€": "EUR",
  USD: "USD",
  DOLLAR: "USD",
  "US DOLLAR": "USD",
  "AMERIKAI DOLLAR": "USD",
  $: "USD",
};

/** Üres -> forint; a magyar és rövidített alakokat is felismeri. Amit nem
 * ismer, azt nagybetűsítve adja vissza - a hibát a szerver mondja ki, nem itt
 * nyeljük el. */
export function penznemKod(penznem: string | null | undefined): string {
  const szoveg = (penznem ?? "").trim();
  if (!szoveg) return "HUF";
  const kulcs = normalizal(szoveg).toUpperCase();
  return PENZNEM_ALIASZOK[kulcs] ?? szoveg.toUpperCase();
}

export function devizas(penznem: string | null | undefined): boolean {
  return penznemKod(penznem) !== "HUF";
}

/** Összeg a saját pénznemében: forintnál a tömör "1,2M Ft" alak, devizánál a
 * teljes szám a kóddal ("1 500 EUR") - egy devizás összeg nem elég nagy ahhoz,
 * hogy rövidíteni kelljen, viszont a pontossága számít. */
export function penzzel(osszeg: number | null, penznem: string | null | undefined): string {
  if (osszeg === null) return "–";
  if (!devizas(penznem)) return formatHuf(osszeg);
  return `${osszeg.toLocaleString("hu-HU")} ${penznemKod(penznem)}`;
}

/** MIBŐL lett a forint összeg - egy soros magyarázat a devizás tételek alá.
 *
 * Múlt idejű, mert a felvezetés tényét írja le, nem a mindenkori összeget: a
 * forint összeg utólag javítható anélkül, hogy ez változna (lásd backend
 * services/penznem.valtsd_at). `null`, ha a tétel eleve forintos volt. */
export function devizaNyom(sor: {
  eredeti_penznem: string | null;
  eredeti_netto: number | null;
  arfolyam: number | null;
}): string | null {
  if (!sor.eredeti_penznem || sor.eredeti_netto === null) return null;
  const arfolyam = sor.arfolyam === null ? "?" : sor.arfolyam.toLocaleString("hu-HU");
  return `${sor.eredeti_netto.toLocaleString("hu-HU")} ${sor.eredeti_penznem} × ${arfolyam}`;
}

/** MIBŐL lett a projektkód forintos BEVÉTELE, ha devizás munka.
 *
 * A bevétel és a profit mindenhol forint - a könyvelésünk abban vezet, és az
 * összesítők egy pénznemet ismernek. Devizás munkánál viszont a puszta szám
 * nem ellenőrizhető: egy át NEM váltott 318 ugyanúgy néz ki, mint egy szokásos
 * forintos összeg. Ez a sor teszi láthatóvá az átváltást.
 *
 * Árfolyam nélkül nincs forintos bevétel (a backend ilyenkor nullát ad, lásd
 * services/projektkod_osszeg.forintban) - ezt ki is mondjuk, mert enélkül egy
 * megmagyarázhatatlan 0 Ft állna a kártyán. */
export function bevetelDevizaNyom(
  deviza: { penznem: string; netto: number; arfolyam: number | null } | null | undefined,
): string | null {
  if (!deviza) return null;
  const kod = penznemKod(deviza.penznem);
  const osszeg = `${deviza.netto.toLocaleString("hu-HU")} ${kod}`;
  if (deviza.arfolyam === null) return `${osszeg} – hiányzik az árfolyam`;
  return `${osszeg} × ${deviza.arfolyam.toLocaleString("hu-HU")} Ft/${kod}`;
}
