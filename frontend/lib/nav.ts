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
    ],
  },
  {
    label: "Ügyfelek",
    items: [{ label: "Ügyfelek", href: "/ugyfelek", icon: "Users" }],
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
      { label: "Leltározás", href: "/felszereles/leltarazas", icon: "ClipboardList", permissionPage: "/felszereles" },
    ],
  },
  {
    label: "Naptár / Diszpó",
    items: [{ label: "Diszpó", href: "/naptar", icon: "Send" }],
  },
  {
    label: "Utómunka",
    items: [{ label: "Deliverable-ök", href: "/utomunka", icon: "Clapperboard" }],
  },
  {
    label: "Média & Portál",
    items: [{ label: "Portál", href: "/media-portal", icon: "Globe" }],
  },
  {
    label: "Pénzügyek",
    items: [
      { label: "Pénzügyek", href: "/penzugyek", icon: "Wallet" },
      { label: "Keretszerződések", href: "/penzugyek/keretszerzodesek", icon: "FileSignature", permissionPage: "/penzugyek" },
    ],
  },
  {
    label: null,
    items: [
      { label: "Alvállalkozók szerződése", href: "/alvallalkozoi-szerzodesek", icon: "FileCheck2" },
      { label: "Teljesítési igazolások", href: "/teljesitesi-igazolasok", icon: "BadgeCheck" },
      { label: "Utókövetés", href: "/utokovetes", icon: "History" },
      { label: "Kampányok", href: "/kampanyok", icon: "Megaphone" },
      { label: "Feladatok", href: "/feladatok", icon: "CheckSquare" },
      { label: "AI Assistant", href: "/ai-assistant", icon: "Sparkles" },
      { label: "Beállítások", href: "/beallitasok", icon: "Settings" },
    ],
  },
];
