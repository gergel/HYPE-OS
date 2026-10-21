/** Az árajánlat-szerkesztő adatszerkezete - ez utazik egyben a backend
 * `Arajanlat.adat` JSON mezőjében (lásd backend models/arajanlat.py).
 *
 * A számok SZÖVEGKÉNT állnak benne ("40 000"), ahogy a mezőben látszanak -
 * az összegzés olvasáskor értelmezi őket (lásd szamErtek), így a gépelés
 * közbeni fél-kész állapot ("40 0") sem dob hibát, és a mentett ajánlat
 * pontosan úgy nyílik vissza, ahogy hagyták. */

export type ArajanlatTetelSor = {
  id: string;
  nev: string;
  megjegyzes: string;
  /** Hány alkalom (pl. 2 forgatási nap) - a szorzat első tagja. */
  alkalom: string;
  mennyiseg: string;
  egysegar: string;
};

export type ArajanlatSzekcio = {
  id: string;
  nev: string;
  tetelek: ArajanlatTetelSor[];
};

export type ArajanlatBlokk = {
  id: string;
  cim: string;
  leiras: string;
  szekciok: ArajanlatSzekcio[];
};

export type ArajanlatAdat = {
  szam: string;
  kelt: string;
  ervenyes: string;
  penznem: string;
  cegnev: string;
  cegadatok: string;
  cimzettNev: string;
  cimzettAdatok: string;
  kapcsolatNev: string;
  kapcsolatAdatok: string;
  blokkok: ArajanlatBlokk[];
  kedvezmeny: string;
  afaLatszik: boolean;
  afa: string;
  /** Soronként egy pont - a lapon lista lesz belőle. */
  tartalmazza: string;
  feltetelek: string;
  alairo: string;
  megrendeloSor: string;
  labCeg: string;
  labBank: string;
};

export const BRAND_BEALLITAS: Record<string, { nev: string; logo: string; cegnev: string }> = {
  hype: { nev: "HYPE", logo: "/arajanlat-hype-logo.png", cegnev: "HYPE Productions Kft." },
  contentbee: { nev: "ContentBee", logo: "/arajanlat-contentbee-logo.png", cegnev: "ContentBee" },
};

let szamlalo = 0;
export function ujId(): string {
  szamlalo += 1;
  return `${Date.now().toString(36)}-${szamlalo}`;
}

/** "40 000" / "1,5" / "1.5" -> szám; értelmezhetetlen -> 0. Ugyanaz a
 * türelmes olvasás, mint a feltöltött sablon val() függvénye. */
export function szamErtek(szoveg: string): number {
  let nyers = String(szoveg ?? "").replace(/[^0-9.,-]/g, "");
  if (nyers.includes(",") && nyers.includes(".")) nyers = nyers.replace(/\./g, "");
  nyers = nyers.replace(",", ".");
  const n = parseFloat(nyers);
  return Number.isFinite(n) ? n : 0;
}

/** Forintra pontos megjelenítés, ezres tagolással (nincs rövidítés - lásd
 * lib/penz.formatHuf, ugyanaz az elv). */
export function osszegSzoveg(n: number): string {
  if (!Number.isFinite(n)) n = 0;
  return Math.round(n).toLocaleString("hu-HU");
}

export function uresTetel(): ArajanlatTetelSor {
  return { id: ujId(), nev: "", megjegyzes: "", alkalom: "1", mennyiseg: "1", egysegar: "0" };
}

export function uresSzekcio(nev = ""): ArajanlatSzekcio {
  return { id: ujId(), nev, tetelek: [uresTetel()] };
}

export function uresBlokk(): ArajanlatBlokk {
  return { id: ujId(), cim: "", leiras: "", szekciok: [uresSzekcio("Technika")] };
}

export function uresAjanlat(brand: string): ArajanlatAdat {
  const b = BRAND_BEALLITAS[brand] ?? BRAND_BEALLITAS.hype;
  const ma = new Date();
  const datum = `${ma.getFullYear()}.${String(ma.getMonth() + 1).padStart(2, "0")}.${String(ma.getDate()).padStart(2, "0")}.`;
  return {
    szam: `${ma.getFullYear()}/`,
    kelt: datum,
    ervenyes: "30 napig",
    penznem: "Ft",
    cegnev: b.cegnev,
    cegadatok: "",
    cimzettNev: "",
    cimzettAdatok: "",
    kapcsolatNev: "",
    kapcsolatAdatok: "",
    blokkok: [uresBlokk()],
    kedvezmeny: "0",
    afaLatszik: false,
    afa: "27",
    tartalmazza:
      "Teljes technikai park és kiszállás\nForgatás egy helyszínen\nVágás, színkorrekció, hangkeverés\nEgy körös korrektúra anyagonként",
    feltetelek:
      "Fizetés: 50% előleg, 50% átadáskor\nFizetési határidő: 8 nap\nLeadás: a forgatástól számított 10 munkanap\nAz ajánlat a fenti dátumig érvényes",
    alairo: "Ajánlatadó",
    megrendeloSor: "Megrendelő · dátum",
    labCeg: b.cegnev,
    labBank: "",
  };
}

/** A mentett JSON türelmes visszaolvasása: ami hiányzik, azt az üres ajánlat
 * értékei pótolják - egy régebbi mentés új mező bevezetése után is megnyílik. */
export function ajanlatAdatBetoltes(nyers: unknown, brand: string): ArajanlatAdat {
  const alap = uresAjanlat(brand);
  if (!nyers || typeof nyers !== "object") return alap;
  const a = { ...alap, ...(nyers as Partial<ArajanlatAdat>) };
  if (!Array.isArray(a.blokkok) || a.blokkok.length === 0) a.blokkok = [uresBlokk()];
  a.blokkok = a.blokkok.map((bl) => ({
    id: bl.id || ujId(),
    cim: bl.cim ?? "",
    leiras: bl.leiras ?? "",
    szekciok: (Array.isArray(bl.szekciok) && bl.szekciok.length > 0 ? bl.szekciok : [uresSzekcio()]).map(
      (sz) => ({
        id: sz.id || ujId(),
        nev: sz.nev ?? "",
        tetelek: (Array.isArray(sz.tetelek) ? sz.tetelek : []).map((t) => ({
          id: t.id || ujId(),
          nev: t.nev ?? "",
          megjegyzes: t.megjegyzes ?? "",
          alkalom: String(t.alkalom ?? "1"),
          mennyiseg: String(t.mennyiseg ?? "1"),
          egysegar: String(t.egysegar ?? "0"),
        })),
      }),
    ),
  }));
  return a;
}

export function tetelOsszeg(t: ArajanlatTetelSor): number {
  return szamErtek(t.alkalom) * szamErtek(t.mennyiseg) * szamErtek(t.egysegar);
}

export function szekcioOsszeg(sz: ArajanlatSzekcio): number {
  return sz.tetelek.reduce((s, t) => s + tetelOsszeg(t), 0);
}

export function blokkOsszeg(bl: ArajanlatBlokk): number {
  return bl.szekciok.reduce((s, sz) => s + szekcioOsszeg(sz), 0);
}

export function osszesites(adat: ArajanlatAdat) {
  const reszosszeg = adat.blokkok.reduce((s, bl) => s + blokkOsszeg(bl), 0);
  const kedvezmeny = (reszosszeg * szamErtek(adat.kedvezmeny)) / 100;
  const netto = reszosszeg - kedvezmeny;
  const afa = adat.afaLatszik ? (netto * szamErtek(adat.afa)) / 100 : 0;
  return { reszosszeg, kedvezmeny, netto, afa, fizetendo: netto + afa };
}
