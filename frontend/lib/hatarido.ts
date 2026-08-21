/** MENNYI IDŐ van a kifizetésig - vagy mennyivel csúszott.
 *
 * Egy fizetési határidő önmagában néma dátum: hogy sürgős-e, azt csak a mai
 * naphoz képest lehet megmondani, és ezt eddig fejben kellett kiszámolni
 * minden soron. A számítás a backendben van (lásd
 * models/project_code.hatarido_allas), itt csak a MONDAT készül belőle - egy
 * helyen, hogy a lista és az adatlap ugyanazt mondja.
 *
 * A napok előjele mindkét irányban ugyanazt jelenti: POZITÍV = jó irány (van
 * még idő / hamarabb fizettek), NEGATÍV = csúszás. */

export type HataridoAllas = {
  /** var | ma_jar_le | lejart | elore_fizetve | hatarido_napjan | keson_fizetve | kifizetve */
  allapot: string;
  napok: number | null;
  hatarido: string;
};

/** Amin belül már figyelmeztetünk: egy héten belüli határidőnél érdemes
 * ránézni, hogy kiment-e a számla. */
const SURGOS_NAP = 7;

export function hataridoSzoveg(allas: HataridoAllas | null | undefined): string | null {
  if (!allas) return null;
  const n = allas.napok;
  switch (allas.allapot) {
    case "var":
      return n === 1 ? "Még 1 nap a kifizetésig" : `Még ${n} nap a kifizetésig`;
    case "ma_jar_le":
      return "Ma jár le a fizetési határidő";
    case "lejart": {
      const napja = Math.abs(n ?? 0);
      return napja === 1 ? "1 napja lejárt a határidő" : `${napja} napja lejárt a határidő`;
    }
    case "elore_fizetve":
      return `${n} nappal a határidő előtt fizetve`;
    case "hatarido_napjan":
      return "Pont a határidőn fizetve";
    case "keson_fizetve": {
      const keses = Math.abs(n ?? 0);
      return `${keses} nappal a határidő után fizetve`;
    }
    // Kifizetve, de dátum nélkül (tranzakció nélküli lezárás) - a határidőhöz
    // nincs mit mérni, tehát nem is állítunk semmit róla.
    default:
      return null;
  }
}

/** Milyen HANGSÚLLYAL - ugyanabból az egy szabályból, mint a szöveg.
 *
 * A lejárt tétel teendő (piros), a közelgő figyelmeztetés (sárga), a késve
 * beérkezett pénz már csak tapasztalat (semleges): utólag nincs mit tenni
 * vele, de a megrendelőről elmond valamit. */
export function hataridoHangsuly(
  allas: HataridoAllas | null | undefined,
): "danger" | "warning" | "success" | "neutral" | null {
  if (!allas) return null;
  switch (allas.allapot) {
    case "lejart":
      return "danger";
    case "ma_jar_le":
      return "warning";
    case "var":
      return (allas.napok ?? 0) <= SURGOS_NAP ? "warning" : "neutral";
    case "keson_fizetve":
      return "neutral";
    case "elore_fizetve":
    case "hatarido_napjan":
      return "success";
    default:
      return null;
  }
}
