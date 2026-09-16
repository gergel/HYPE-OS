/** A "HYPE OS" szöveges logó - a Sidebar ÉS a MobileNav fejlécében is
 * ugyanez, hogy a fiók megnyitva is a szokott felületnek hasson.
 *
 * A hivatalos logó vektoros újraépítése (a felhasználó csatolt képei
 * alapján): tömör, vastag "HYPE" felirat + KONTÚROS "OS", keret nélkül.
 * Betűkörvonalakká alakítva - így nem függ a betöltött betűtípusoktól, és
 * nincs mögötte háttér. A színe currentColor: a szülő szövegszínét veszi
 * fel, ezért világos témán a fekete, sötét témán a fehér változat jelenik
 * meg külön képfájl nélkül. */
export function Logo({ className = "h-6" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 4943 812"
      fill="none"
      className={`${className} w-auto text-text-primary`}
      role="img"
      aria-label="HYPE OS"
    >
      {/* HYPE - tömör */}
      <path
        fill="currentColor"
        d="M600 750V489H357V750H136V62H357V313H600V62H821V750Z M1396 750H1175V483L902 62H1156L1288 291H1292L1424 62H1665L1396 483Z M2353 288V301Q2353 365 2325.0 417.0Q2297 469 2247.0 498.5Q2197 528 2133 528H1968V750H1747V62H2133Q2197 62 2247.0 91.5Q2297 121 2325.0 172.5Q2353 224 2353 288ZM1968 367H2059Q2094 367 2111.5 349.0Q2129 331 2129 300V292Q2129 260 2111.5 242.5Q2094 225 2059 225H1968Z M2469 62H3064V227H2690V322H3010V480H2690V585H3071V750H2469Z"
      />
      {/* OS - csak körvonal */}
      <g transform="translate(3544 750) scale(0.86)">
        <path
          fill="none"
          stroke="currentColor"
          strokeWidth="36"
          d="M788 -344Q788 -170 691.0 -79.0Q594 12 416 12Q238 12 141.5 -78.5Q45 -169 45 -344Q45 -519 141.5 -609.5Q238 -700 416 -700Q594 -700 691.0 -609.0Q788 -518 788 -344ZM271 -376V-312Q271 -239 308.0 -196.0Q345 -153 416 -153Q487 -153 524.5 -196.0Q562 -239 562 -312V-376Q562 -449 524.5 -492.0Q487 -535 416 -535Q345 -535 308.0 -492.0Q271 -449 271 -376Z M1500 -488V-476H1293V-480Q1293 -510 1271.0 -530.0Q1249 -550 1204 -550Q1160 -550 1136.5 -537.0Q1113 -524 1113 -505Q1113 -478 1145.0 -465.0Q1177 -452 1248 -438Q1331 -421 1384.5 -402.5Q1438 -384 1478.0 -342.0Q1518 -300 1519 -228Q1519 -106 1436.5 -47.0Q1354 12 1216 12Q1055 12 965.5 -42.0Q876 -96 876 -233H1085Q1085 -181 1112.0 -163.5Q1139 -146 1196 -146Q1238 -146 1265.5 -155.0Q1293 -164 1293 -192Q1293 -217 1262.5 -229.5Q1232 -242 1163 -256Q1079 -274 1024.0 -293.5Q969 -313 928.0 -358.0Q887 -403 887 -480Q887 -593 974.5 -646.5Q1062 -700 1196 -700Q1328 -700 1413.0 -646.5Q1498 -593 1500 -488Z"
        />
      </g>
    </svg>
  );
}
