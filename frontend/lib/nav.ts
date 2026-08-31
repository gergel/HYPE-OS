export type NavItem = {
  label: string;
  href: string;
  /** lucide-react ikonnév (lásd Sidebar.tsx ICONS map) - soronként egy ikon,
   * a referencia dizájn mintájára. */
  icon?: string;
  /** A backend page_permissions kulcsa, ami TÉNYLEGESEN védi ezt az oldalt
   * (lásd backend `page=`/`PAGE` értékek a build_crud_router/require_page_action
   * hívásokban). Ha nincs megadva, a href maga a kulcs - ez a leggyakoribb eset
   * (1 nav-elem = 1 önálló backend jogosultság). Csak akkor kell explicit
   * módon megadni, ha ez a nav-elem egy MÁSIK, közös backend jogosultságot
   * oszt meg több nav-elemmel is (pl. Vágók/Belsősök a Külsőssel közösen
   * "/csapat", mert mind ugyanaz az Employee-router; vagy Leltározás a
   * "/felszereles"-sel, mert a stocktake.py is azt használja) - FONTOS: ha itt
   * hibás/hiányzó az érték, az vagy túl szigorú (feleslegesen külön
   * jogosultságot igényel), vagy túl megengedő (egy másik oldal jogosultsága
   * is beengedi) lesz, ezért mindig a backend `page=`/`PAGE` konstanssal kell
   * egyeznie. */
  permissionPage?: string;
  /** Ha meg van adva, a menüpont csak akkor látszik, ha a felhasználónak ez a
   * MŰVELETE is megvan az oldalon (nem elég a puszta nézési jog). Olyan
   * elemekhez kell, amik nem nézegetni valók, hanem egy munkafolyamatot
   * indítanak - pl. a Leltározás, ami a leltár szerkesztése. Enélkül az, aki
   * csak nézheti az eszközöket (pl. a diszpós, aki a projekten technikát vezet
   * fel - lásd core/security.OLDAL_ALIASZOK), egy zsákutcát látna a menüben. */
  permissionAction?: "edit" | "create" | "delete";
};

export type NavGroup = {
  label: string | null;
  items: NavItem[];
};

export type PagePermissionGroup = { page: string; label: string };

/** Egy jogosultsági "oldal" a nav-elemek explicit permissionPage mezője (vagy
 * ha az nincs megadva, a href) alapján - lásd NavItem.permissionPage
 * kommentje. Egy csoporton belül csak akkor kapnak KÖZÖS címkét (a csoport
 * nevét) a nav-elemek, ha ténylegesen ugyanazt a jogosultsági kulcsot osztják
 * (pl. Külsős/Vágók/Belsősök mind "/csapat") - ha egy csoporton belül eltérő
 * kulcsuk van (pl. Projektek/Project Code-ok, amik KÜLÖN backend
 * jogosultságok), mindegyik a saját nevén, külön sorban jelenik meg. Lásd
 * UserAccessManager - a Beállítások oldal ez alapján sorolja fel a per-oldal
 * megtekintés/szerkesztés/létrehozás/törlés checkboxokat. */
/** Jogosultsági oldalak, amiknek NINCS bejegyzésük az oldalsávban.
 *
 * A Krumpello nem a HYPE OS egyik menüpontja, hanem egy külön felület, amire
 * a fejlécben ülő kapcsoló visz át (lásd components/KrumpelloKapcsolo.tsx) -
 * a saját navigációját már ő maga hozza. A jogosultságának viszont ugyanúgy
 * meg kell jelennie a Beállítások oldalon, hogy admin egyenként adhassa meg,
 * ki lássa egyáltalán a kapcsolót.
 *
 * A middleware-nek nem kell külön kezelnie: a resolvePermissionPage
 * visszaesése az útvonal első szeletét adja ("/krumpello"), ami pont ez a
 * kulcs - ugyanaz, amit a backend is használ (routes/krumpello.py PAGE). */
export const KULON_JOGOSULTSAGOK: PagePermissionGroup[] = [
  { page: "/krumpello", label: "Krumpello (külön pénzügy)" },
];

export function pagePermissionGroups(): PagePermissionGroup[] {
  const seen = new Set<string>();
  const result: PagePermissionGroup[] = [];
  for (const group of navGroups) {
    const pageOf = (item: NavItem) => item.permissionPage ?? item.href;
    for (const item of group.items) {
      const page = pageOf(item);
      if (seen.has(page)) continue;
      seen.add(page);
      const sharedCount = group.items.filter((i) => pageOf(i) === page).length;
      result.push({ page, label: sharedCount > 1 ? (group.label ?? item.label) : item.label });
    }
  }
  for (const kulon of KULON_JOGOSULTSAGOK) {
    if (!seen.has(kulon.page)) result.push(kulon);
  }
  return result;
}

/** Egy URL-útvonalhoz tartozó jogosultsági "oldal" kulcs meghatározása - a
 * LEGHOSSZABB egyező nav-item href-et keressük (ugyanaz a mintázat, mint a
 * Sidebar aktív-állapot logikája), majd annak permissionPage-ét (vagy magát a
 * href-et) adjuk vissza. Ez teszi lehetővé, hogy pl.
 * "/projektek/project-kodok/123" (egy Project Code részletnézete) a "Project
 * Code-ok" jogosultsághoz kerüljön, NE a "Projektek"-hez, annak ellenére,
 * hogy az URL-je a "/projektek" alatt van - és fordítva, hogy
 * "/csapat/vagok/456" helyesen a közös "/csapat" backend-jogosultsághoz
 * legyen kötve. A middleware.ts (a tényleges navigáció-blokkoláshoz) ezt
 * használja, hogy sose térjen el a Sidebar/Settings által mutatott
 * jogosultságoktól. */
export function resolvePermissionPage(pathname: string): string {
  const allItems = navGroups.flatMap((group) => group.items);
  const match = allItems
    .filter((item) => pathname === item.href || pathname.startsWith(item.href + "/"))
    .sort((a, b) => b.href.length - a.href.length)[0];
  if (match) return match.permissionPage ?? match.href;
  return "/" + (pathname.split("/").filter(Boolean)[0] ?? "");
}

export const navGroups: NavGroup[] = [
  { label: null, items: [{ label: "Dashboard", href: "/dashboard", icon: "LayoutDashboard" }] },
  {
    label: "Projektek",
    items: [
      { label: "Project Code-ok", href: "/projektek/project-kodok", icon: "Hash" },
      { label: "Projektek", href: "/projektek", icon: "FolderKanban" },
      // A megrendelői papírok a projektkódhoz tartoznak, ezért ugyanaz a
      // backend jogosultság védi őket (lásd routes/megrendeloi_papirok.py PAGE).
      {
        label: "Megrendelői keretszerződések",
        href: "/projektek/megrendeloi-keretszerzodesek",
        icon: "FileSignature",
        permissionPage: "/projektek/project-kodok",
      },
      {
        label: "Megrendelői szerződések",
        href: "/projektek/megrendeloi-szerzodesek",
        icon: "FileText",
        permissionPage: "/projektek/project-kodok",
      },
      {
        label: "Megrendelői TIG-ek",
        href: "/projektek/megrendeloi-tigek",
        icon: "FileCheck2",
        permissionPage: "/projektek/project-kodok",
      },
    ],
  },
  {
    label: "Ügyfelek",
    items: [
      { label: "Ügyfelek", href: "/ugyfelek", icon: "Users" },
      // A kontaktok az ügyfelek adatához tartoznak (ugyanaz a jogosultság),
      // csak önálló nézetet kaptak: itt lehet rákeresni valakire anélkül,
      // hogy tudnánk, melyik cégnél van.
      {
        label: "Megrendelői kontaktok",
        href: "/megrendeloi-kontaktok",
        icon: "Contact",
        permissionPage: "/ugyfelek",
      },
    ],
  },
  {
    label: "Csapat",
    items: [
      { label: "Külsős", href: "/csapat", icon: "UserRound" },
      { label: "Vágók", href: "/csapat/vagok", icon: "Scissors", permissionPage: "/csapat" },
      { label: "Belsősök", href: "/csapat/belsosok", icon: "UserCheck", permissionPage: "/csapat" },
    ],
  },
  {
    label: "Felszerelés",
    items: [
      { label: "Eszközök", href: "/felszereles", icon: "Package" },
      {
        label: "Leltározás",
        href: "/felszereles/leltarazas",
        icon: "ClipboardList",
        permissionPage: "/felszereles",
        permissionAction: "edit",
      },
    ],
  },
  {
    label: "Naptár / Diszpó",
    items: [
      { label: "Diszpó", href: "/naptar", icon: "Send" },
      // A Google Sheetből átvett HYPE 2026 táblázat - a cellák SZÍNE itt adat
      // (ki melyik nap dolgozott), lásd backend models/diszpo_tabla.py.
      { label: "HYPE 2026 tábla", href: "/diszpo-tabla", icon: "Table" },
    ],
  },
  {
    label: "Utómunka",
    items: [
      { label: "Utómunka", href: "/utomunka", icon: "Clapperboard" },
      // A vágói visszajelzések ugyanannak az oldalnak a jogosultságával
      // olvashatók, csak külön nézetben gyűlnek.
      {
        label: "Vágói visszajelzések",
        href: "/utomunka/visszajelzesek",
        icon: "MessageSquare",
        permissionPage: "/utomunka",
      },
    ],
  },
  {
    label: "Média & Portál",
    items: [{ label: "Portál", href: "/media-portal", icon: "Globe" }],
  },
  {
    label: "Pénzügyek",
    items: [
      { label: "Pénzügyek", href: "/penzugyek", icon: "Wallet" },
      // A kassza "főkönyve": minden készpénz-mozgás időrendben, futó
      // egyenleggel - ide kell jönni, ha a dobozban más van, mint amit a
      // rendszer mond.
      { label: "KP forgalom", href: "/penzugyek/kp-forgalom", icon: "Coins", permissionPage: "/penzugyek" },
      { label: "Keretszerződések", href: "/penzugyek/keretszerzodesek", icon: "FileSignature", permissionPage: "/penzugyek" },
      { label: "Eseti szerződések", href: "/penzugyek/eseti-szerzodesek", icon: "FileText", permissionPage: "/penzugyek" },
      // Számlázó cégek: akik EMBEREKET küldenek a forgatásra, és a munkájukról
      // ők számláznak (lásd backend services/szamlazo.py).
      { label: "Számlázó cégek", href: "/penzugyek/vallalkozasok", icon: "Building2", permissionPage: "/penzugyek" },
    ],
  },
  {
    // Ami magától visszatér vagy lejár: előfizetések és az autók papírjai.
    // Mindkettő ugyanazon a motoron fut (lásd backend
    // services/kotelezettseg.py) - a felület azért külön, hogy a havi
    // szolgáltatások ne folyjanak össze az évente lejáró papírokkal.
    //
    // Külön "Biztosítások" oldal NINCS: a biztosítás mindig egy autóhoz
    // tartozik, és ott is kell kezelni - lásd /autok.
    //
    // Az E-Rezsi és az Autók KÜLÖN jogosultság (a felhasználó kérése) - a
    // közös kötelezettség-motor kulcsát (/kotelezettsegek) mindkét oldal
    // saját joga aliaszon át nyitja meg, és a régi /kotelezettsegek grantok
    // is tovább működnek (lásd lib/permissions.OLDAL_ALIASZOK).
    label: "Kötelezettségek",
    items: [
      { label: "E-Rezsi", href: "/e-rezsi", icon: "Repeat" },
      { label: "Autók", href: "/autok", icon: "Car" },
    ],
  },
  {
    label: null,
    items: [
      // Az "Alvállalkozók szerződése" és a "Teljesítési igazolások" külön
      // menüpont megszűnt: az Utókövetés oldal a kettőt EGYBEN kezeli
      // (projektenként, egymás mellett látszik, mi hiányzik még). A hozzájuk
      // tartozó műveletek megmaradtak, csak a jogosultságuk az Utókövetés
      // oldalé lett (lásd backend subcontractor_contracts.py /
      // performance_certificates.py PAGE konstansa).
      { label: "Belsős TIG", href: "/belsos-tig", icon: "BadgeCheck" },
      { label: "Utókövetés", href: "/utokovetes", icon: "History" },
      // Az összes külsős TIG egy listában, a kihagyottakkal együtt. Ugyanaz a
      // backend jogosultság, mint az Utókövetésé (a TIG-műveletek oda
      // tartoznak, lásd backend performance_certificates.py PAGE).
      {
        label: "Külsős TIG-ek",
        href: "/utokovetes/kulsos-tigek",
        icon: "FileCheck2",
        permissionPage: "/utokovetes",
      },
      // A vágói játék az utómunkához tartozik, de SAJÁT jogosultsága van: az
      // állás mindenkinek látszik, akit beengedünk (a verseny lényege, hogy
      // lássák egymást), a nyeremény és a munkanapok viszont adminé.
      { label: "Vágói játék", href: "/vagoi-jatek", icon: "Trophy" },
      { label: "Kampányok", href: "/kampanyok", icon: "Megaphone" },
      { label: "Feladatok", href: "/feladatok", icon: "CheckSquare" },
      // A Notion "HYPE TO-DO LIST", "FLÓRA" és "ÁGI" oldalainak átvétele -
      // önálló táblák, NEM a fenti Feladatok (Task) oldal része (lásd backend
      // models/hype_todo.py, models/flora_feladat.py, models/agi_todo.py
      // megjegyzését arról, miért nem a régi, félbehagyott Task-egyesítést
      // folytattuk). Az ÁGI oldal a saját To-Do listája MELLETT a meglévő,
      // élő Utómunka táblát és Forgatások naptárt is beágyazva mutatja.
      { label: "HYPE TO-DO LIST", href: "/hype-todo-lista", icon: "ListChecks" },
      { label: "FLÓRA", href: "/flora", icon: "Palette" },
      { label: "ÁGI", href: "/agi", icon: "Sparkle" },
      { label: "AI Assistant", href: "/ai-assistant", icon: "Sparkles" },
      { label: "Beállítások", href: "/beallitasok", icon: "Settings" },
    ],
  },
];
