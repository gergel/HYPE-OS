export type NavItem = {
  label: string;
  href: string;
  /** lucide-react ikonnév (lásd Sidebar.tsx ICONS map) - soronként egy ikon,
   * a referencia dizájn mintájára. */
  icon?: string;
};

export type NavGroup = {
  label: string | null;
  items: NavItem[];
};

export type PagePermissionGroup = { page: string; label: string };

/** Egy jogosultsági "oldal" per topSegment (ugyanaz a granularitás, amit a
 * middleware.ts topSegment-alapú navigáció-szűrése és a backend
 * check_page_action-je használ) - egy csoporton belüli összes nav item
 * ugyanazt a topSegmentet osztja (pl. "Project Code-ok" és "Projektek" is
 * "/projektek"), ezért egyetlen checkbox-szal (a csoport címkéjével)
 * reprezentáljuk; a címke nélküli (önálló) itemek a saját címkéjüket adják.
 * Lásd UserAccessManager - a Beállítások oldal ez alapján sorolja fel a
 * per-oldal megtekintés/szerkesztés/létrehozás/törlés checkboxokat. */
export function pagePermissionGroups(): PagePermissionGroup[] {
  const seen = new Set<string>();
  const result: PagePermissionGroup[] = [];
  for (const group of navGroups) {
    for (const item of group.items) {
      const topSegment = "/" + item.href.split("/").filter(Boolean)[0];
      if (seen.has(topSegment)) continue;
      seen.add(topSegment);
      result.push({ page: topSegment, label: group.label ?? item.label });
    }
  }
  return result;
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
      { label: "Vágók", href: "/csapat/vagok", icon: "Scissors" },
      { label: "Belsősök", href: "/csapat/belsosok", icon: "UserCheck" },
    ],
  },
  {
    label: "Felszerelés",
    items: [
      { label: "Eszközök", href: "/felszereles", icon: "Package" },
      { label: "Leltározás", href: "/felszereles/leltarazas", icon: "ClipboardList" },
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
      { label: "Keretszerződések", href: "/penzugyek/keretszerzodesek", icon: "FileSignature" },
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
