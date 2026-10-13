"use client";

/** AZ AUTÓ KÖRVONALA FELÜLNÉZETBEN (a felhasználó kérése: mint a MOL
 * Limónál - az autó körvonalán kell rányomni arra a részére, amelyikről a
 * fotó készül). Az eleje van fent; a hét koppintható rész: az eleje, a
 * hátulja, a két oldala, az első és a hátsó üléssor, a csomagtartó (furgonnál
 * a raktér).
 *
 * Három karosszéria-forma van (személyautó, SUV, kisbusz/furgon - lásd
 * backend services/auto_allapot.karosszeria). A kész részek zöldek, a
 * kiválasztott kiemelt; `kamera`-val egy jelölő mutatja, honnan kell
 * fotózni (útmutató). */

export type Karosszeria = "szemelyauto" | "suv" | "furgon";

type Geo = {
  bal: number;
  jobb: number;
  teteje: number;
  alja: number;
  rx: number;
  eleje: number; // az eleje-zóna alja
  hatulja: number; // a hátulja-zóna teteje
  szelvedo: [number, number];
  elso: [number, number];
  hatso: [number, number];
  hatsoAblak: [number, number] | null;
  csomag: [number, number];
  kerekek: [number, number];
  elsoUlesDb: number;
};

const GEO: Record<Karosszeria, Geo> = {
  szemelyauto: {
    bal: 72, jobb: 188, teteje: 40, alja: 460, rx: 48, eleje: 118, hatulja: 412,
    szelvedo: [126, 158], elso: [166, 226], hatso: [242, 296], hatsoAblak: [304, 332], csomag: [340, 406],
    kerekek: [108, 368], elsoUlesDb: 2,
  },
  suv: {
    bal: 66, jobb: 194, teteje: 40, alja: 460, rx: 36, eleje: 108, hatulja: 414,
    szelvedo: [114, 144], elso: [152, 212], hatso: [228, 284], hatsoAblak: null, csomag: [296, 408],
    kerekek: [102, 372], elsoUlesDb: 2,
  },
  furgon: {
    bal: 60, jobb: 200, teteje: 34, alja: 466, rx: 22, eleje: 84, hatulja: 424,
    szelvedo: [88, 112], elso: [118, 168], hatso: [180, 232], hatsoAblak: null, csomag: [246, 418],
    kerekek: [92, 388], elsoUlesDb: 3,
  },
};

export const OLDAL_SORREND = ["eleje", "hatulja", "bal_oldal", "jobb_oldal", "csomagtarto", "elso_ulesek", "hatso_ulesek"];

/** A rész felirata - furgonnál a csomagtartó: raktér. */
export function reszCimke(oldal: string, karosszeria: Karosszeria, alap: string): string {
  if (oldal === "csomagtarto" && karosszeria === "furgon") return "Raktér";
  return alap;
}

/** Útmutató: honnan és mit fotózzon. */
export function utmutato(oldal: string, karosszeria: Karosszeria): string {
  const furgon = karosszeria === "furgon";
  switch (oldal) {
    case "eleje":
      return "Állj az autó elé kb. 2–3 méterre, hogy az egész eleje beférjen: lökhárító, lámpák, motorháztető.";
    case "hatulja":
      return "Állj az autó mögé kb. 2–3 méterre, hogy a teljes hátulja beférjen: lökhárító, lámpák, ajtó.";
    case "bal_oldal":
      return "Állj a bal (vezetőoldali) oldalával szemben, olyan messze, hogy az elejétől a végéig beférjen.";
    case "jobb_oldal":
      return "Állj a jobb (utasoldali) oldalával szemben, olyan messze, hogy az elejétől a végéig beférjen.";
    case "csomagtarto":
      return furgon
        ? "Nyisd ki a raktér ajtaját, és fotózd be a teljes rakteret."
        : "Nyisd ki a csomagtartót, és fotózd be a teljes csomagteret.";
    case "elso_ulesek":
      return "Nyisd ki a vezetőoldali ajtót, és fotózd le az első üléssort.";
    case "hatso_ulesek":
      return furgon
        ? "Nyisd ki az oldalsó tolóajtót, és fotózd le a hátsó üléssort."
        : "Nyisd ki a bal hátsó ajtót, és fotózd le a hátsó üléssort.";
    default:
      return "";
  }
}

function reszStilus(kesz: boolean, kivalasztott: boolean): string {
  if (kivalasztott) return "fill-text-blue/35 stroke-text-blue";
  if (kesz) return "fill-text-success/25 stroke-text-success";
  return "fill-transparent stroke-text-muted/70 hover:fill-text-accent/10";
}

function Pipa({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`} className="pointer-events-none">
      <circle r={8} className="fill-text-success" />
      <path d="M -3.5 0 l 2.5 2.6 l 4.5 -5" className="fill-none stroke-surface-1" strokeWidth={2} strokeLinecap="round" />
    </g>
  );
}

export function AutoKorvonal({
  karosszeria,
  kesz = {},
  kivalasztott = null,
  onValaszt,
  kamera = null,
  cimkek = true,
  className = "",
  cimkeSzoveg,
}: {
  karosszeria: Karosszeria;
  kesz?: Record<string, boolean>;
  kivalasztott?: string | null;
  onValaszt?: (oldal: string) => void;
  /** Útmutatóhoz: honnan fotózzon (jelölő a kép mellett). */
  kamera?: string | null;
  cimkek?: boolean;
  className?: string;
  /** A részek feliratai (kulcs -> szöveg). */
  cimkeSzoveg?: Record<string, string>;
}) {
  const g = GEO[karosszeria] ?? GEO.szemelyauto;
  const kozep = (g.bal + g.jobb) / 2;
  const szel = g.jobb - g.bal;
  const oldalTeteje = g.eleje + 6;
  const oldalAlja = g.hatulja - 6;
  const oldalKozep = (oldalTeteje + oldalAlja) / 2;
  const kattinthato = !!onValaszt;
  const clipId = `karosszeria-${karosszeria}`;

  const resz = (oldal: string) => ({
    className: `${reszStilus(!!kesz[oldal], kivalasztott === oldal)} ${kattinthato ? "cursor-pointer" : ""} transition-colors`,
    strokeWidth: kivalasztott === oldal ? 2.5 : 1.2,
    strokeDasharray: kesz[oldal] || kivalasztott === oldal ? undefined : "4 3",
    onClick: kattinthato ? () => onValaszt?.(oldal) : undefined,
    role: kattinthato ? "button" : undefined,
    "aria-label": kattinthato ? cimkeSzoveg?.[oldal] ?? oldal : undefined,
    tabIndex: kattinthato ? 0 : undefined,
    onKeyDown: kattinthato
      ? (e: React.KeyboardEvent) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onValaszt?.(oldal);
          }
        }
      : undefined,
  });

  const felirat = (oldal: string, x: number, y: number, forgat = 0) =>
    cimkek ? (
      <text
        x={x}
        y={y}
        transform={forgat ? `rotate(${forgat} ${x} ${y})` : undefined}
        textAnchor="middle"
        dominantBaseline="middle"
        className="pointer-events-none fill-text-primary text-[11px] font-medium"
      >
        {cimkeSzoveg?.[oldal] ?? oldal}
      </text>
    ) : null;

  // A kamera-jelölő helye részenként (honnan kell fotózni).
  const kameraHely: Record<string, [number, number, number, number]> = {
    eleje: [kozep, g.teteje - 22, kozep, g.teteje + 6],
    hatulja: [kozep, g.alja + 22, kozep, g.alja - 6],
    bal_oldal: [g.bal - 44, oldalKozep, g.bal - 18, oldalKozep],
    jobb_oldal: [g.jobb + 44, oldalKozep, g.jobb + 18, oldalKozep],
    elso_ulesek: [g.bal - 44, (g.elso[0] + g.elso[1]) / 2, g.bal + 14, (g.elso[0] + g.elso[1]) / 2],
    hatso_ulesek: [g.bal - 44, (g.hatso[0] + g.hatso[1]) / 2, g.bal + 14, (g.hatso[0] + g.hatso[1]) / 2],
    csomagtarto: [kozep, g.alja + 22, kozep, g.csomag[1] - 8],
  };

  const ulesek = (y: [number, number], db: number) => {
    const belsoBal = g.bal + 22;
    const belsoSzel = szel - 44;
    const res = 6;
    const w = (belsoSzel - res * (db - 1)) / db;
    return Array.from({ length: db }, (_, i) => (
      <rect
        key={i}
        x={belsoBal + i * (w + res)}
        y={y[0] + 8}
        width={w}
        height={y[1] - y[0] - 16}
        rx={7}
        className="pointer-events-none fill-surface-3 stroke-border"
        strokeWidth={1}
      />
    ));
  };

  return (
    <svg viewBox="0 0 260 500" className={className} role={kattinthato ? "group" : "img"} aria-label="Az autó körvonala felülnézetben">
      <defs>
        <clipPath id={clipId}>
          <rect x={g.bal} y={g.teteje} width={szel} height={g.alja - g.teteje} rx={g.rx} />
        </clipPath>
      </defs>

      {/* Kerekek (a karosszéria alól kilógva) és tükrök. */}
      {g.kerekek.map((y) => (
        <g key={y} className="fill-text-muted/60">
          <rect x={g.bal - 9} y={y - 24} width={14} height={48} rx={5} />
          <rect x={g.jobb - 5} y={y - 24} width={14} height={48} rx={5} />
        </g>
      ))}
      <ellipse cx={g.bal - 6} cy={g.szelvedo[0] + 4} rx={9} ry={5} className="fill-text-muted/60" />
      <ellipse cx={g.jobb + 6} cy={g.szelvedo[0] + 4} rx={9} ry={5} className="fill-text-muted/60" />

      {/* Karosszéria */}
      <rect
        x={g.bal}
        y={g.teteje}
        width={szel}
        height={g.alja - g.teteje}
        rx={g.rx}
        className="fill-surface-2 stroke-text-muted"
        strokeWidth={1.5}
      />
      {/* Szélvédő és hátsó ablak */}
      <path
        d={`M ${g.bal + 12} ${g.szelvedo[1]} L ${g.bal + 22} ${g.szelvedo[0]} L ${g.jobb - 22} ${g.szelvedo[0]} L ${g.jobb - 12} ${g.szelvedo[1]} Z`}
        className="pointer-events-none fill-surface-3"
      />
      {g.hatsoAblak && (
        <path
          d={`M ${g.bal + 14} ${g.hatsoAblak[0]} L ${g.jobb - 14} ${g.hatsoAblak[0]} L ${g.jobb - 22} ${g.hatsoAblak[1]} L ${g.bal + 22} ${g.hatsoAblak[1]} Z`}
          className="pointer-events-none fill-surface-3"
        />
      )}

      {/* ELEJE és HÁTULJA - a karosszéria formájára vágva */}
      <g clipPath={`url(#${clipId})`}>
        <rect x={g.bal} y={g.teteje} width={szel} height={g.eleje - g.teteje} {...resz("eleje")} />
        <rect x={g.bal} y={g.hatulja} width={szel} height={g.alja - g.hatulja} {...resz("hatulja")} />
      </g>
      {felirat("eleje", kozep, (g.teteje + g.eleje) / 2 + 4)}
      {felirat("hatulja", kozep, (g.hatulja + g.alja) / 2 - 2)}

      {/* OLDALAK - keskeny sáv a karosszéria két szélén */}
      <rect x={g.bal - 16} y={oldalTeteje} width={28} height={oldalAlja - oldalTeteje} rx={10} {...resz("bal_oldal")} />
      <rect x={g.jobb - 12} y={oldalTeteje} width={28} height={oldalAlja - oldalTeteje} rx={10} {...resz("jobb_oldal")} />
      {felirat("bal_oldal", g.bal - 2, oldalKozep, -90)}
      {felirat("jobb_oldal", g.jobb + 2, oldalKozep, 90)}

      {/* BELSŐ: első és hátsó üléssor, csomagtartó / raktér */}
      {ulesek(g.elso, g.elsoUlesDb)}
      {ulesek(g.hatso, 1)}
      <rect x={g.bal + 16} y={g.elso[0]} width={szel - 32} height={g.elso[1] - g.elso[0]} rx={10} {...resz("elso_ulesek")} />
      <rect x={g.bal + 16} y={g.hatso[0]} width={szel - 32} height={g.hatso[1] - g.hatso[0]} rx={10} {...resz("hatso_ulesek")} />
      <rect x={g.bal + 16} y={g.csomag[0]} width={szel - 32} height={g.csomag[1] - g.csomag[0]} rx={10} {...resz("csomagtarto")} />
      {felirat("elso_ulesek", kozep, (g.elso[0] + g.elso[1]) / 2)}
      {felirat("hatso_ulesek", kozep, (g.hatso[0] + g.hatso[1]) / 2)}
      {felirat("csomagtarto", kozep, (g.csomag[0] + g.csomag[1]) / 2)}

      {/* Pipák a kész részeken */}
      {kesz.eleje && <Pipa x={g.jobb - 22} y={g.teteje + 18} />}
      {kesz.hatulja && <Pipa x={g.jobb - 22} y={g.alja - 18} />}
      {kesz.bal_oldal && <Pipa x={g.bal - 2} y={oldalTeteje + 14} />}
      {kesz.jobb_oldal && <Pipa x={g.jobb + 2} y={oldalTeteje + 14} />}
      {kesz.elso_ulesek && <Pipa x={g.jobb - 26} y={g.elso[0] + 12} />}
      {kesz.hatso_ulesek && <Pipa x={g.jobb - 26} y={g.hatso[0] + 12} />}
      {kesz.csomagtarto && <Pipa x={g.jobb - 26} y={g.csomag[0] + 12} />}

      {/* Útmutató: a kamera helye és iránya */}
      {kamera && kameraHely[kamera] && (
        <g className="pointer-events-none">
          <line
            x1={kameraHely[kamera][0]}
            y1={kameraHely[kamera][1]}
            x2={kameraHely[kamera][2]}
            y2={kameraHely[kamera][3]}
            className="stroke-text-accent"
            strokeWidth={2}
            strokeDasharray="4 3"
          />
          <g transform={`translate(${kameraHely[kamera][0]} ${kameraHely[kamera][1]})`}>
            <circle r={14} className="fill-bg-accent stroke-text-accent" strokeWidth={2} />
            <rect x={-7} y={-5} width={14} height={10} rx={2} className="fill-text-accent" />
            <rect x={-3} y={-8} width={6} height={3} rx={1} className="fill-text-accent" />
            <circle r={3} className="fill-bg-accent" />
          </g>
        </g>
      )}
    </svg>
  );
}
